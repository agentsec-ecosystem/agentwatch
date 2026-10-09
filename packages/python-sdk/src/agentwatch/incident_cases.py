"""Incident cases: merged, gap-annotated timeline + offline case bundle (M30 IR-1, #473).

PRD 57 §IR-1, design [incident-cases](../../../../docs/design/incident-cases.md).

A real incident spans sessions, hosts, people and days; a single session's
timeline is not an incident. A **case** is a named grouping of sessions recorded
as metadata-only append-only **chain records** (the same pattern holds use, PRD
56 §HLD-1): ``create`` / ``add`` / ``remove`` events each land in the store's
hash chain, so membership cannot be edited after the fact without breaking it.

``case_timeline`` merges the member sessions into one ordered timeline, states
its **ordering rules**, and **classifies gaps** (explicit ``recording-gap``
records, tombstones, purges, unreadable lines, and inter-record time gaps).

``build_case_bundle`` packages the case (timeline + per-session verdicts + a
COR-3-shaped incident report) with its chain segment so it **verifies offline**,
and it is **manual**: the bundle is written locally and nowhere else — there is
no registry egress path.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentwatch.incident_report import build_incident_report
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)
from agentwatch.session_export import export_session, verify_export
from agentwatch.store import MARKER_PRODUCER, RecordStore
from agentwatch.union import source_of

CASE_TOOL = "incident-case"
CASE_BUNDLE_FORMAT = "agentwatch-case-bundle/1"
CASE_BUNDLE_FORMAT_VERSION = 1
CASE_REPORT_SCHEMA = "agentwatch.case-incident-report/1"
DEFAULT_GAP_SECONDS = 3600.0

_ORDERING = (
    "ascending started_at (UTC); tie-break session_id, then chain seq"
)
_GAP_TOOL = "recording-gap"
_PURGE_TOOL = "session-purge"


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _ndjson_bytes(rows: list[dict[str, Any]]) -> bytes:
    text = "\n".join(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows) + "\n"
    return text.encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tool_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("agentwatch")
    except PackageNotFoundError:  # pragma: no cover - source checkout
        return "0.1.0"


# --------------------------------------------------------------------------- model


@dataclass(frozen=True)
class CaseMember:
    """One session's membership in a case, with the chain record that added it."""

    session_id: str
    added_at: datetime
    seq: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "added_at": self.added_at.isoformat(),
            "seq": self.seq,
        }


@dataclass(frozen=True)
class IncidentCase:
    """A named case and its current membership (read back from the chain)."""

    case_id: str
    title: str
    severity: str
    ref: str | None
    created_at: datetime
    create_seq: int
    members: tuple[CaseMember, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "severity": self.severity,
            "ref": self.ref,
            "created_at": self.created_at.isoformat(),
            "create_seq": self.create_seq,
            "members": [member.to_dict() for member in self.members],
        }


@dataclass(frozen=True)
class CaseMarker:
    """One recorded case event (create/add/remove), for auditing."""

    seq: int
    action: str
    case_id: str
    session_id: str | None
    title: str | None
    severity: str | None
    ref: str | None
    at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "action": self.action,
            "case_id": self.case_id,
            "session_id": self.session_id,
            "title": self.title,
            "severity": self.severity,
            "ref": self.ref,
            "at": self.at.isoformat(),
        }


@dataclass(frozen=True)
class TimelineEntry:
    """One merged-timeline row: a member session's record with its chain position."""

    at: datetime
    session_id: str
    seq: int
    source: str
    tool: str
    outcome: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "at": self.at.isoformat(),
            "session_id": self.session_id,
            "seq": self.seq,
            "source": self.source,
            "tool": self.tool,
            "outcome": self.outcome,
        }


@dataclass(frozen=True)
class TimelineGap:
    """A classified gap in the merged timeline (never silent)."""

    kind: str
    at: datetime | None
    session_id: str | None
    detail: str
    seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "at": self.at.isoformat() if self.at else None,
            "session_id": self.session_id,
            "detail": self.detail,
            "seconds": self.seconds,
        }


@dataclass(frozen=True)
class CaseTimeline:
    """A case's merged timeline: ordering rule, entries, and classified gaps."""

    case_id: str
    ordering: str
    entries: tuple[TimelineEntry, ...]
    gaps: tuple[TimelineGap, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "ordering": self.ordering,
            "entries": [entry.to_dict() for entry in self.entries],
            "gaps": [gap.to_dict() for gap in self.gaps],
        }


def _case_marker(
    action: str,
    arguments: dict[str, Any],
    moment: datetime,
) -> AgentRecord:
    return AgentRecord(
        session_id="agentwatch",
        agent=AgentIdentity(identity="agentwatch"),
        tool=ToolCall(
            name=CASE_TOOL,
            arguments={"action": action, **arguments},
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
        outcome=Outcome.OK,
        started_at=moment,
        producer=MARKER_PRODUCER,
    )


# --------------------------------------------------------------------------- writing


def _known_case_ids(store: RecordStore) -> set[str]:
    return {
        str((entry.record.tool.arguments or {}).get("case_id", ""))
        for entry in store.entries()
        if entry.record is not None and entry.record.tool.name == CASE_TOOL
        and (entry.record.tool.arguments or {}).get("action") == "create"
    }


def record_case_create(
    store: RecordStore,
    *,
    title: str,
    severity: str = "medium",
    ref: str | None = None,
    now: datetime | None = None,
) -> IncidentCase:
    """Append a case-create record; the case ID is a stable per-store counter (``C<n>``)."""
    moment = now or datetime.now(timezone.utc)
    case_id = f"C{len(_known_case_ids(store)) + 1}"
    entry = store.append(
        _case_marker(
            "create",
            {"case_id": case_id, "title": title, "severity": severity, "ref": ref},
            moment,
        )
    )
    return IncidentCase(
        case_id=case_id,
        title=title,
        severity=severity,
        ref=ref,
        created_at=moment,
        create_seq=entry.seq,
    )


def record_case_add(
    store: RecordStore,
    case_id: str,
    session_id: str,
    *,
    now: datetime | None = None,
) -> CaseMarker:
    """Add a session to a case as a chain record; unknown cases fail closed."""
    if case_id not in _known_case_ids(store):
        raise ValueError(f"unknown case {case_id!r}")
    moment = now or datetime.now(timezone.utc)
    entry = store.append(
        _case_marker("add", {"case_id": case_id, "session_id": session_id}, moment)
    )
    return CaseMarker(
        seq=entry.seq,
        action="add",
        case_id=case_id,
        session_id=session_id,
        title=None,
        severity=None,
        ref=None,
        at=moment,
    )


def record_case_remove(
    store: RecordStore,
    case_id: str,
    session_id: str,
    *,
    now: datetime | None = None,
) -> CaseMarker:
    """Remove a session from a case as a chain record; unknown cases fail closed."""
    if case_id not in _known_case_ids(store):
        raise ValueError(f"unknown case {case_id!r}")
    moment = now or datetime.now(timezone.utc)
    entry = store.append(
        _case_marker("remove", {"case_id": case_id, "session_id": session_id}, moment)
    )
    return CaseMarker(
        seq=entry.seq,
        action="remove",
        case_id=case_id,
        session_id=session_id,
        title=None,
        severity=None,
        ref=None,
        at=moment,
    )


# --------------------------------------------------------------------------- reading


def case_markers(store: RecordStore) -> list[CaseMarker]:
    """Every recorded case event, in chain order (create/add/remove)."""
    markers: list[CaseMarker] = []
    for entry in store.entries():
        record = entry.record
        if record is None or record.tool.name != CASE_TOOL:
            continue
        arguments = record.tool.arguments or {}
        action = str(arguments.get("action", ""))
        if action not in {"create", "add", "remove"}:
            continue
        markers.append(
            CaseMarker(
                seq=entry.seq,
                action=action,
                case_id=str(arguments.get("case_id", "")),
                session_id=(
                    str(arguments["session_id"]) if arguments.get("session_id") else None
                ),
                title=str(arguments["title"]) if arguments.get("title") else None,
                severity=str(arguments["severity"]) if arguments.get("severity") else None,
                ref=str(arguments["ref"]) if arguments.get("ref") else None,
                at=record.started_at,
            )
        )
    return markers


def active_cases(store: RecordStore) -> list[IncidentCase]:
    """Reconstruct every case and its current membership from the chain."""
    cases: dict[str, IncidentCase] = {}
    members: dict[str, list[CaseMember]] = {}
    for marker in case_markers(store):
        if marker.action == "create":
            cases[marker.case_id] = IncidentCase(
                case_id=marker.case_id,
                title=marker.title or "",
                severity=marker.severity or "medium",
                ref=marker.ref,
                created_at=marker.at,
                create_seq=marker.seq,
            )
            members[marker.case_id] = []
        elif marker.case_id not in cases:
            continue
        elif marker.action == "add" and marker.session_id is not None:
            current = members[marker.case_id]
            if all(member.session_id != marker.session_id for member in current):
                current.append(CaseMember(marker.session_id, marker.at, marker.seq))
        elif marker.action == "remove" and marker.session_id is not None:
            members[marker.case_id] = [
                member
                for member in members[marker.case_id]
                if member.session_id != marker.session_id
            ]
    return [
        IncidentCase(
            case_id=case.case_id,
            title=case.title,
            severity=case.severity,
            ref=case.ref,
            created_at=case.created_at,
            create_seq=case.create_seq,
            members=tuple(members[case.case_id]),
        )
        for case in cases.values()
    ]


def _find_case(store: RecordStore, case_id: str) -> IncidentCase:
    for case in active_cases(store):
        if case.case_id == case_id:
            return case
    raise ValueError(f"unknown case {case_id!r}")


def case_timeline(
    store: RecordStore,
    case_id: str,
    *,
    gap_seconds: float = DEFAULT_GAP_SECONDS,
) -> CaseTimeline:
    """Merge the member sessions, state the ordering rule, and classify gaps."""
    case = _find_case(store, case_id)
    member_ids = {member.session_id for member in case.members}

    entries: list[TimelineEntry] = []
    gaps: list[TimelineGap] = []
    for entry in store.entries():
        record = entry.record
        if record is None or record.session_id not in member_ids:
            continue
        entries.append(
            TimelineEntry(
                at=record.started_at,
                session_id=record.session_id,
                seq=entry.seq,
                source=source_of(record),
                tool=record.tool.name,
                outcome=record.outcome.value,
            )
        )
        if record.tool.name == _GAP_TOOL:
            gaps.append(
                TimelineGap(
                    kind="recording-gap",
                    at=record.started_at,
                    session_id=record.session_id,
                    detail=f"explicit recording gap at seq {entry.seq}",
                )
            )
        elif record.tool.name == _PURGE_TOOL:
            gaps.append(
                TimelineGap(
                    kind="purge",
                    at=record.started_at,
                    session_id=record.session_id,
                    detail=f"session purged (tombstone written) at seq {entry.seq}",
                )
            )
    entries.sort(key=lambda item: (item.at, item.session_id, item.seq))

    for earlier, later in zip(entries, entries[1:], strict=False):
        delta = (later.at - earlier.at).total_seconds()
        if delta > gap_seconds:
            gaps.append(
                TimelineGap(
                    kind="time-gap",
                    at=later.at,
                    session_id=later.session_id,
                    detail=(
                        f"no records for {delta:.0f}s between "
                        f"{earlier.session_id}:{earlier.seq} and {later.session_id}:{later.seq}"
                    ),
                    seconds=delta,
                )
            )

    for entry in store.entries():
        if entry.tombstone:
            gaps.append(
                TimelineGap(
                    kind="tombstone",
                    at=None,
                    session_id=None,
                    detail=(
                        f"store tombstone at seq {entry.seq} (payload dropped; "
                        "attribution unavailable)"
                    ),
                )
            )
    for line_number in store.parse_error_lines:
        gaps.append(
            TimelineGap(
                kind="unreadable",
                at=None,
                session_id=None,
                detail=f"unreadable chain line {line_number}",
            )
        )

    gaps.sort(key=lambda gap: (gap.at or case.created_at, gap.kind, gap.detail))
    return CaseTimeline(
        case_id=case.case_id,
        ordering=_ORDERING,
        entries=tuple(entries),
        gaps=tuple(gaps),
    )


def render_case_timeline(timeline: CaseTimeline) -> str:
    """Render the merged timeline as text, stating the ordering rule and gaps."""
    lines = [
        f"agentwatch case {timeline.case_id} — merged timeline",
        f"  ordering: {timeline.ordering}",
        f"  entries : {len(timeline.entries)}",
    ]
    for entry in timeline.entries:
        lines.append(
            f"  {entry.at.isoformat()} [{entry.session_id}] seq {entry.seq} "
            f"{entry.tool} ({entry.outcome}, {entry.source})"
        )
    lines.append(f"  gaps    : {len(timeline.gaps)}")
    for gap in timeline.gaps:
        lines.append(f"    - {gap.kind}: {gap.detail}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- bundle


@dataclass(frozen=True)
class CaseBundle:
    """An in-memory case bundle: member name -> bytes, plus its case id."""

    case_id: str
    members: dict[str, bytes] = field(default_factory=dict)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(self.members):
                archive.writestr(name, self.members[name])
        tmp.replace(path)


def _verdicts(store: RecordStore, case: IncidentCase) -> dict[str, dict[str, Any]]:
    verdicts: dict[str, dict[str, Any]] = {}
    for member in case.members:
        rows = [entry.record for entry in store.entries() if entry.record is not None]
        count = sum(1 for record in rows if record.session_id == member.session_id)
        verdicts[member.session_id] = {
            "intact": store.verify().ok,
            "records": count,
        }
    return verdicts


def build_case_bundle(
    store: RecordStore,
    case_id: str,
    *,
    now: datetime | None = None,
) -> CaseBundle:
    """Assemble a self-contained, offline-verifiable case bundle."""
    moment = now or datetime.now(timezone.utc)
    case = _find_case(store, case_id)
    timeline = case_timeline(store, case_id)

    rows: list[dict[str, Any]] = []
    for member in case.members:
        export = export_session(store, member.session_id)
        rows.extend(dict(row) for row in export.rows)
    rows.sort(key=lambda row: int(row["seq"]))

    reports = [
        build_incident_report(store, member.session_id, now=moment)
        for member in case.members
    ]
    incident_report = {
        "schema": CASE_REPORT_SCHEMA,
        "case_id": case.case_id,
        "generated_at": moment.isoformat(),
        "submission": {"mode": "manual-voluntary", "endpoint": None, "auto_egress": False},
        "reports": reports,
    }

    members: dict[str, bytes] = {
        "records.ndjson": _ndjson_bytes(rows),
        "case.json": _json_bytes(
            {
                "schema": CASE_BUNDLE_FORMAT,
                "case": case.to_dict(),
                "ordering": timeline.ordering,
                "entries": [entry.to_dict() for entry in timeline.entries],
                "gaps": [gap.to_dict() for gap in timeline.gaps],
                "verdicts": _verdicts(store, case),
            }
        ),
        "incident-report.json": _json_bytes(incident_report),
    }
    manifest = {
        "bundle_format": CASE_BUNDLE_FORMAT,
        "bundle_format_version": CASE_BUNDLE_FORMAT_VERSION,
        "created_at": moment.isoformat(),
        "tool_version": _tool_version(),
        "case_id": case.case_id,
        "members": {name: _sha256(data) for name, data in members.items()},
    }
    members["manifest.json"] = _json_bytes(manifest)
    return CaseBundle(case_id=case.case_id, members=members)


@dataclass(frozen=True)
class CaseBundleVerification:
    """The independent verdict on a case bundle (offline, no store)."""

    bundle_format: str
    intact: bool
    problems: tuple[str, ...] = ()
    case_id: str = ""

    @property
    def ok(self) -> bool:
        return self.intact and not self.problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_format": self.bundle_format,
            "case_id": self.case_id,
            "intact": self.intact,
            "problems": list(self.problems),
        }


def verify_case_bundle(path: Path | str) -> CaseBundleVerification:
    """Re-verify a case bundle offline: member hashes and the chain segment."""
    bundle_path = Path(path)
    problems: list[str] = []
    try:
        with zipfile.ZipFile(bundle_path) as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names:
                return CaseBundleVerification(CASE_BUNDLE_FORMAT, False, ("manifest.json missing",))
            manifest = json.loads(archive.read("manifest.json"))
            bundle_format = str(manifest.get("bundle_format", ""))
            case_id = str(manifest.get("case_id", ""))
            if bundle_format != CASE_BUNDLE_FORMAT:
                return CaseBundleVerification(
                    bundle_format,
                    False,
                    (f"unknown bundle format version {bundle_format!r}",),
                    case_id,
                )
            recorded: dict[str, str] = manifest.get("members", {})
            for name, digest in recorded.items():
                if name not in names:
                    problems.append(f"member missing: {name}")
                    continue
                if _sha256(archive.read(name)) != digest:
                    problems.append(f"member tampered: {name}")
            segment_ok = _verify_segment(archive.read("records.ndjson"), problems)
    except (zipfile.BadZipFile, OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        return CaseBundleVerification(CASE_BUNDLE_FORMAT, False, (f"unreadable bundle: {exc}",))

    intact = segment_ok and not any(
        "tampered" in problem or "missing" in problem for problem in problems
    )
    return CaseBundleVerification(
        bundle_format=bundle_format,
        intact=intact,
        problems=tuple(problems),
        case_id=case_id,
    )


def _verify_segment(data: bytes, problems: list[str]) -> bool:
    rows: list[dict[str, Any]] = []
    for line in data.decode("utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    if not verify_export(rows):
        problems.append("case chain segment failed verification")
        return False
    return True


__all__ = [
    "CASE_BUNDLE_FORMAT",
    "CASE_BUNDLE_FORMAT_VERSION",
    "CASE_REPORT_SCHEMA",
    "CASE_TOOL",
    "DEFAULT_GAP_SECONDS",
    "CaseBundle",
    "CaseBundleVerification",
    "CaseMarker",
    "CaseMember",
    "CaseTimeline",
    "IncidentCase",
    "TimelineEntry",
    "TimelineGap",
    "active_cases",
    "build_case_bundle",
    "case_markers",
    "case_timeline",
    "record_case_add",
    "record_case_create",
    "record_case_remove",
    "render_case_timeline",
    "verify_case_bundle",
]
