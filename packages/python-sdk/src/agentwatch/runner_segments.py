"""Sealed runner segments + ``import-segment`` custody (M30 RUN-1, #479).

PRD 58 §RUN-1, design [runner-segments](../../../../docs/design/runner-segments.md).

Background/cloud agents run where agentwatch has no daemon or home. A **sealed
segment** is a self-contained capture an ephemeral runner writes and uploads as
a CI artifact: its **own** hash chain over the run's records, the **runner
identity**, and a start/end **attestation**. agentwatch performs no egress — the
user moves the artifact.

``import_segment`` verifies the segment chain and attestation and **anchors** it
into the local store as a ``source: runner`` chain-of-custody record, then
appends the records. Imported records are **chain-protected** (they are in the
local chain) but **not locally witnessed**, and are labelled so at every surface
(the same S11 integrity distinction ``union`` uses). A ``traceparent`` joins the
runner session to its originating local session; the custody statement travels
with the join. Only redacted records are sealed or imported.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    Producer,
    ProducerKind,
    RecordPrivacyMode,
    ToolCall,
    effective_producer,
    validate_record,
)
from agentwatch.store import GENESIS_HASH, MARKER_PRODUCER, RecordStore
from agentwatch.trace_context import parse_traceparent

SEGMENT_FORMAT = "agentwatch-runner-segment/1"
SEGMENT_FORMAT_VERSION = 1
SEGMENT_TOOL = "runner-segment"
RUNNER_PRODUCER_NAME = "runner-segment"


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _ndjson_bytes(rows: list[dict[str, Any]]) -> bytes:
    text = "\n".join(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows) + "\n"
    return text.encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _row_hash(prev_hash: str, record: dict[str, Any]) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256((prev_hash + canonical).encode("utf-8")).hexdigest()


def _assert_redacted(records: list[AgentRecord]) -> None:
    for record in records:
        if record.tool.privacy_mode is RecordPrivacyMode.FULL:
            raise ValueError(
                f"refusing to handle unredacted record {record.tool.name!r} "
                "(privacy_mode=full); redacted records only"
            )


# --------------------------------------------------------------------------- sealing


@dataclass(frozen=True)
class SealedSegment:
    """An in-memory sealed segment: member name -> bytes, plus its identity."""

    runner: str
    run_id: str
    members: dict[str, bytes] = field(default_factory=dict)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(self.members):
                archive.writestr(name, self.members[name])
        tmp.replace(path)


def seal_segment(
    records: list[AgentRecord],
    *,
    runner: str,
    run_id: str,
    started_at: datetime,
    ended_at: datetime,
    traceparent: str | None = None,
    now: datetime | None = None,
) -> SealedSegment:
    """Seal a run's records into a self-verifying segment with its own chain."""
    _assert_redacted(records)
    moment = now or datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    prev = GENESIS_HASH
    for index, record in enumerate(records):
        payload = record.to_dict()
        digest = _row_hash(prev, payload)
        rows.append({"record": payload, "seq": index, "prev_hash": prev, "hash": digest})
        prev = digest

    members: dict[str, bytes] = {
        "records.ndjson": _ndjson_bytes(rows),
        "segment.json": _json_bytes(
            {
                "schema": SEGMENT_FORMAT,
                "runner": {"id": runner},
                "run_id": run_id,
                "started_at": started_at.isoformat(),
                "ended_at": ended_at.isoformat(),
                "traceparent": traceparent,
                "records": len(rows),
            }
        ),
        "attestation.json": _json_bytes(
            {
                "schema": "agentwatch.runner-attestation/1",
                "present": True,
                "runner": runner,
                "run_id": run_id,
                "started_at": started_at.isoformat(),
                "ended_at": ended_at.isoformat(),
            }
        ),
    }
    manifest = {
        "bundle_format": SEGMENT_FORMAT,
        "bundle_format_version": SEGMENT_FORMAT_VERSION,
        "created_at": moment.isoformat(),
        "runner": runner,
        "run_id": run_id,
        "members": {name: _sha256(data) for name, data in members.items()},
    }
    members["manifest.json"] = _json_bytes(manifest)
    return SealedSegment(runner=runner, run_id=run_id, members=members)


# --------------------------------------------------------------------------- verification


@dataclass(frozen=True)
class SegmentVerification:
    """The independent verdict on a runner segment (offline, no store)."""

    bundle_format: str
    intact: bool
    attestation: str
    runner: str = ""
    run_id: str = ""
    sessions: tuple[str, ...] = ()
    traceparent: str | None = None
    first_broken: int | None = None
    problems: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.intact and not self.problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_format": self.bundle_format,
            "intact": self.intact,
            "attestation": self.attestation,
            "runner": self.runner,
            "run_id": self.run_id,
            "sessions": list(self.sessions),
            "traceparent": self.traceparent,
            "first_broken": self.first_broken,
            "problems": list(self.problems),
        }


def _verify_chain(data: bytes, problems: list[str]) -> tuple[bool, int | None]:
    rows: list[dict[str, Any]] = []
    for line in data.decode("utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    prev = GENESIS_HASH
    for index, row in enumerate(rows):
        record = row.get("record")
        if not isinstance(record, dict):
            problems.append(f"segment row {index} has no record")
            return False, index
        if int(row.get("seq", -1)) != index or row.get("prev_hash") != prev:
            return False, index
        if _row_hash(prev, record) != row.get("hash"):
            return False, index
        prev = str(row["hash"])
    return True, None


def _sessions(rows: list[dict[str, Any]]) -> tuple[str, ...]:
    sessions = {
        str(row["record"]["session_id"])
        for row in rows
        if isinstance(row.get("record"), dict) and row["record"].get("session_id")
    }
    return tuple(sorted(sessions))


def verify_segment(path: Path | str) -> SegmentVerification:
    """Re-verify a segment offline: member hashes, its own chain, and attestation."""
    segment_path = Path(path)
    problems: list[str] = []
    try:
        with zipfile.ZipFile(segment_path) as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names:
                return SegmentVerification("", False, "absent", problems=("manifest.json missing",))
            manifest = json.loads(archive.read("manifest.json"))
            bundle_format = str(manifest.get("bundle_format", ""))
            if bundle_format != SEGMENT_FORMAT:
                return SegmentVerification(
                    bundle_format,
                    False,
                    "absent",
                    problems=(f"unknown segment format version {bundle_format!r}",),
                )
            recorded: dict[str, str] = manifest.get("members", {})
            for name, digest in recorded.items():
                if name not in names:
                    problems.append(f"member missing: {name}")
                    continue
                if _sha256(archive.read(name)) != digest:
                    problems.append(f"member tampered: {name}")
            segment = json.loads(archive.read("segment.json"))
            runner = str((segment.get("runner") or {}).get("id", ""))
            run_id = str(segment.get("run_id", ""))
            traceparent = segment.get("traceparent")
            attestation = _attestation_state(archive, names)
            if attestation != "present":
                problems.append("attestation absent")
            chain_ok, first_broken = _verify_chain(archive.read("records.ndjson"), problems)
            rows = [
                json.loads(line)
                for line in archive.read("records.ndjson").decode("utf-8").splitlines()
                if line.strip()
            ]
            sessions = _sessions(rows)
    except (zipfile.BadZipFile, OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        return SegmentVerification("", False, "absent", problems=(f"unreadable segment: {exc}",))

    intact = chain_ok and attestation == "present" and not any(
        "tampered" in problem or "missing" in problem or "no record" in problem
        for problem in problems
    )
    return SegmentVerification(
        bundle_format=bundle_format,
        intact=intact,
        attestation=attestation,
        runner=runner,
        run_id=run_id,
        sessions=sessions,
        traceparent=str(traceparent) if traceparent else None,
        first_broken=first_broken,
        problems=tuple(problems),
    )


def _attestation_state(archive: zipfile.ZipFile, names: set[str]) -> str:
    if "attestation.json" not in names:
        return "absent"
    try:
        payload = json.loads(archive.read("attestation.json"))
    except json.JSONDecodeError:
        return "absent"
    return "present" if payload.get("present") is True else "absent"


# --------------------------------------------------------------------------- import


@dataclass(frozen=True)
class AnchorRecord:
    """A recorded segment-import custody anchor (the local chain-of-custody)."""

    seq: int
    action: str
    runner: str
    run_id: str
    segment_digest: str
    sessions: tuple[str, ...]
    joined_sessions: tuple[str, ...]
    traceparent: str | None
    custody: str
    auto_egress: bool
    destination: str | None
    at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "action": self.action,
            "runner": self.runner,
            "run_id": self.run_id,
            "segment_digest": self.segment_digest,
            "sessions": list(self.sessions),
            "joined_sessions": list(self.joined_sessions),
            "traceparent": self.traceparent,
            "custody": self.custody,
            "auto_egress": self.auto_egress,
            "destination": self.destination,
            "at": self.at.isoformat(),
        }


@dataclass(frozen=True)
class CustodyRow:
    """One record's chain-of-custody label (imported vs locally witnessed)."""

    session_id: str
    seq: int
    source: str
    locally_witnessed: bool
    chain_protected: bool
    tool: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "seq": self.seq,
            "source": self.source,
            "locally_witnessed": self.locally_witnessed,
            "chain_protected": self.chain_protected,
            "tool": self.tool,
        }


@dataclass(frozen=True)
class ImportReport:
    """The outcome of importing one sealed segment."""

    runner: str
    run_id: str
    records: int
    sessions: tuple[str, ...]
    joined_sessions: tuple[str, ...]
    segment_digest: str
    anchor_seq: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "runner": self.runner,
            "run_id": self.run_id,
            "records": self.records,
            "sessions": list(self.sessions),
            "joined_sessions": list(self.joined_sessions),
            "segment_digest": self.segment_digest,
            "anchor_seq": self.anchor_seq,
        }


def _anchor_record(
    *,
    runner: str,
    run_id: str,
    segment_digest: str,
    sessions: tuple[str, ...],
    joined_sessions: tuple[str, ...],
    traceparent: str | None,
    moment: datetime,
) -> AgentRecord:
    custody = (
        "source: runner; imported segment; chain-protected locally but NOT locally witnessed"
    )
    return AgentRecord(
        session_id="agentwatch",
        agent=AgentIdentity(identity="agentwatch"),
        tool=ToolCall(
            name=SEGMENT_TOOL,
            arguments={
                "action": "import",
                "runner": runner,
                "run_id": run_id,
                "segment_digest": segment_digest,
                "sessions": list(sessions),
                "joined_sessions": list(joined_sessions),
                "traceparent": traceparent,
                "custody": custody,
                "auto_egress": False,
                "destination": None,
            },
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
        outcome=Outcome.OK,
        started_at=moment,
        producer=MARKER_PRODUCER,
    )


def _join_sessions(store: RecordStore, traceparent: str | None) -> tuple[str, ...]:
    context = parse_traceparent(traceparent) if traceparent else None
    if context is None:
        return ()
    joined: set[str] = set()
    for record in store.records():
        trace_id = record.trace_id
        if trace_id is None and record.traceparent:
            parsed = parse_traceparent(record.traceparent)
            trace_id = parsed.trace_id if parsed is not None else None
        if trace_id == context.trace_id:
            joined.add(record.session_id)
    return tuple(sorted(joined))


def _read_rows(path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        return [
            json.loads(line)
            for line in archive.read("records.ndjson").decode("utf-8").splitlines()
            if line.strip()
        ]


def import_segment(
    store: RecordStore,
    path: Path | str,
    *,
    now: datetime | None = None,
) -> ImportReport:
    """Verify a segment and anchor it locally as ``source: runner`` custody."""
    segment_path = Path(path)
    data = segment_path.read_bytes()
    digest = _sha256(data)
    verification = verify_segment(segment_path)
    if not verification.intact:
        detail = "; ".join(verification.problems) or "failed verification"
        raise ValueError(f"segment failed verification: {detail}")

    rows = _read_rows(segment_path)
    imported = [validate_record(row["record"]) for row in rows]
    _assert_redacted(imported)

    joined = _join_sessions(store, verification.traceparent)
    moment = now or datetime.now(timezone.utc)
    anchor_entry = store.append(
        _anchor_record(
            runner=verification.runner,
            run_id=verification.run_id,
            segment_digest=digest,
            sessions=verification.sessions,
            joined_sessions=joined,
            traceparent=verification.traceparent,
            moment=moment,
        )
    )
    for record in imported:
        store.append(
            replace(
                record,
                producer=Producer(kind=ProducerKind.IMPORT, name=RUNNER_PRODUCER_NAME),
            )
        )
    return ImportReport(
        runner=verification.runner,
        run_id=verification.run_id,
        records=len(imported),
        sessions=verification.sessions,
        joined_sessions=joined,
        segment_digest=digest,
        anchor_seq=anchor_entry.seq,
    )


# --------------------------------------------------------------------------- custody

_IMPORT_CUSTODY = "source: runner; imported segment; NOT locally witnessed"


def _str_tuple(value: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in value) if isinstance(value, list) else ()


def anchor_records(store: RecordStore) -> list[AnchorRecord]:
    """Every recorded segment-import custody anchor, in chain order."""
    anchors: list[AnchorRecord] = []
    for entry in store.entries():
        record = entry.record
        if record is None or record.tool.name != SEGMENT_TOOL:
            continue
        arguments = record.tool.arguments or {}
        if arguments.get("action") != "import":
            continue
        anchors.append(
            AnchorRecord(
                seq=entry.seq,
                action="import",
                runner=str(arguments.get("runner", "")),
                run_id=str(arguments.get("run_id", "")),
                segment_digest=str(arguments.get("segment_digest", "")),
                sessions=_str_tuple(arguments.get("sessions")),
                joined_sessions=_str_tuple(arguments.get("joined_sessions")),
                traceparent=(
                    str(arguments["traceparent"]) if arguments.get("traceparent") else None
                ),
                custody=str(arguments.get("custody", _IMPORT_CUSTODY)),
                auto_egress=bool(arguments.get("auto_egress", False)),
                destination=(
                    str(arguments["destination"]) if arguments.get("destination") else None
                ),
                at=record.started_at,
            )
        )
    return anchors


def _is_runner_record(record: AgentRecord) -> bool:
    return effective_producer(record).name == RUNNER_PRODUCER_NAME


def custody_rows(store: RecordStore) -> list[CustodyRow]:
    """Every record labelled with its custody: local witness vs imported runner."""
    rows: list[CustodyRow] = []
    for entry in store.entries():
        record = entry.record
        if record is None:
            continue
        imported = _is_runner_record(record)
        rows.append(
            CustodyRow(
                session_id=record.session_id,
                seq=entry.seq,
                source="runner" if imported else "local",
                locally_witnessed=not imported,
                chain_protected=True,
                tool=record.tool.name,
            )
        )
    return rows


def render_custody(store: RecordStore) -> str:
    """Human custody readout; imported records are explicitly not locally witnessed."""
    rows = custody_rows(store)
    lines = [f"agentwatch runner custody: {len(rows)} record(s)"]
    if not rows:
        return "\n".join(lines)
    lines.append("SEQ\tSESSION\tSOURCE\tTOOL\tCUSTODY")
    for row in rows:
        custody = "chain-protected, locally witnessed" if row.locally_witnessed else (
            "chain-protected, NOT locally witnessed"
        )
        lines.append(
            f"{row.seq}\t{row.session_id}\t{row.source}\t{row.tool}\t{custody}"
        )
    if any(not row.locally_witnessed for row in rows):
        lines.append("note: 'source: runner' records are imported and NOT locally witnessed")
    return "\n".join(lines)


__all__ = [
    "RUNNER_PRODUCER_NAME",
    "SEGMENT_FORMAT",
    "SEGMENT_FORMAT_VERSION",
    "SEGMENT_TOOL",
    "AnchorRecord",
    "CustodyRow",
    "ImportReport",
    "SealedSegment",
    "SegmentVerification",
    "anchor_records",
    "custody_rows",
    "import_segment",
    "render_custody",
    "seal_segment",
    "verify_segment",
]
