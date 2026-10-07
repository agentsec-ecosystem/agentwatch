"""``agentwatch evidence`` — a self-contained, offline-verifiable bundle (M15 S1, #231).

An incident owner hands an artifact to legal, an auditor, or a customer, and it
must survive leaving the machine where it was produced. The bundle packages data
already stored — no new capture, no egress — as a versioned, open zip:

``manifest.json`` (format/store/tool versions, schema ids, sha256 of every member),
``records.ndjson`` (session records with their chain envelope), ``chain.json``
(segment + nearest checkpoints), ``verify.json``/``verify.txt`` (chain verdict),
``privacy.json`` (leak-free verdict), ``coverage.json`` (complete verdict),
``inventory.json`` / ``bom.cdx.json``, ``summary.md``, and ``SCHEMA/``.

``agentwatch evidence verify bundle.zip`` re-verifies offline, with no store. The
three verdicts — **intact / complete / leak-free** — are reported independently,
never collapsed.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentwatch.annotate import operator_notes
from agentwatch.bom import build_bom, to_cyclonedx
from agentwatch.denials import denial_sequences
from agentwatch.forensic import statement
from agentwatch.incident_report import INCIDENT_REPORT_FILENAME, build_incident_report
from agentwatch.inventory import build_inventory, inventory_to_json
from agentwatch.records import effective_producer, validate_record
from agentwatch.session_export import export_session
from agentwatch.signing import signing_status
from agentwatch.store import RecordStore
from agentwatch.verify_privacy import verify_privacy

BUNDLE_FORMAT = "agentwatch-evidence/1"
BUNDLE_FORMAT_VERSION = 1


def _row_is_not_demo(row: dict[str, object]) -> bool:
    """Whether an export row is real evidence (synthetic demo rows are excluded)."""
    record = row.get("record")
    if not isinstance(record, dict):
        return True
    producer = record.get("producer")
    if isinstance(producer, dict):
        return producer.get("kind") != "demo"
    return True


_PURGE_TOOL = "session-purge"
_GAP_TOOL = "recording-gap"
_ACCESS_TOOL = "store-access"

_PATH_RE = re.compile(r"(?:/(?:[\w.\-@+]+/)*[\w.\-@+]+|[A-Za-z]:\\[^\s\"']+)")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _ndjson_bytes(rows: list[dict[str, Any]]) -> bytes:
    text = "\n".join(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows) + "\n"
    return text.encode("utf-8")


def _tool_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("agentwatch")
    except PackageNotFoundError:  # pragma: no cover - source checkout
        return "0.1.0"


def _schema_dir() -> Path | None:
    candidate = Path(__file__).resolve()
    for parent in candidate.parents:
        schema = parent / "schema"
        if (schema / "agent-record.schema.json").is_file():
            return schema
    return None


def _redact_paths(value: Any) -> Any:
    if isinstance(value, str):
        return _PATH_RE.sub("<REDACTED:path>", value)
    if isinstance(value, dict):
        return {key: _redact_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_paths(item) for item in value]
    return value


@dataclass(frozen=True)
class EvidenceBundle:
    """An in-memory bundle: member name -> bytes, plus its session id."""

    session_id: str
    members: dict[str, bytes] = field(default_factory=dict)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(self.members):
                archive.writestr(name, self.members[name])
        tmp.replace(path)


def _nearest_checkpoints(store: RecordStore, seqs: list[int]) -> dict[str, Any]:
    checkpoints = store.checkpoints()
    if not checkpoints:
        return {"before": None, "after": None, "anchors_available": False}
    before = next((c for c in checkpoints if c.seq < min(seqs)), None) if seqs else None
    after = next((c for c in reversed(checkpoints) if c.seq > max(seqs)), None) if seqs else None
    return {
        "before": _checkpoint_dict(before),
        "after": _checkpoint_dict(after),
        "anchors_available": before is not None or after is not None,
    }


def _checkpoint_dict(entry: Any) -> dict[str, Any] | None:
    if entry is None:
        return None
    return {
        "seq": entry.seq,
        "prev_hash": entry.prev_hash,
        "hash": entry.hash,
        "entries": entry.entries,
        "at": entry.at,
    }


def _coverage(store: RecordStore, session_id: str, entries: list[Any]) -> dict[str, Any]:
    """A minimal complete-verdict: gaps, tombstones, and purges, enumerated.

    Tombstones keep their chain links but drop the record payload, so a tombstone
    cannot be attributed to one session after the fact; the store-level tombstone
    list is reported as-is, with that limitation stated.
    """
    gaps: list[int] = []
    tombstones: list[int] = []
    purges: list[int] = []
    producers: dict[str, int] = {}
    for entry in store.entries():
        if entry.tombstone:
            tombstones.append(entry.seq)
    for entry in entries:
        record = entry.record
        if record is None:
            continue
        kind = effective_producer(record).kind.value
        producers[kind] = producers.get(kind, 0) + 1
        if record.tool.name == _GAP_TOOL:
            gaps.append(entry.seq)
        elif record.tool.name == _PURGE_TOOL:
            purges.append(entry.seq)
    # Chain-level parse errors are gaps too.
    gaps.extend(store.parse_error_lines)
    return {
        "session_id": session_id,
        "records": sum(1 for e in entries if e.record is not None),
        "producers": dict(sorted(producers.items())),
        "gaps": sorted(set(gaps)),
        "tombstones": sorted(tombstones),
        "tombstone_attribution": "unavailable (payload dropped); store-level list",
        "purges": sorted(purges),
        "complete": not gaps,
    }


def build_bundle(
    store: RecordStore,
    store_path: Path | str,
    session_id: str,
    *,
    include_bom: bool = False,
    redact_paths: bool = False,
    includes: tuple[str, ...] = (),
    now: datetime | None = None,
) -> EvidenceBundle:
    """Assemble a self-contained evidence bundle for one session."""
    moment = now or datetime.now(timezone.utc)
    entries = [
        entry
        for entry in store.entries()
        if entry.record is not None and entry.record.session_id == session_id
    ]
    if not entries and not any(
        entry.record is not None
        and entry.record.session_id == session_id
        and entry.record.tool.name == _PURGE_TOOL
        for entry in store.entries()
    ):
        raise ValueError(f"no records for session {session_id}")

    export = export_session(store, session_id)
    rows = [dict(row) for row in export.rows]
    # Synthetic demo records are never evidence (M19 S31).
    rows = [row for row in rows if _row_is_not_demo(row)]
    if redact_paths:
        for row in rows:
            row["record"] = _redact_paths(row["record"])

    chain_status = store.verify()
    privacy = verify_privacy(store_path)
    coverage = _coverage(store, session_id, entries)
    inventory = build_inventory(store, session_id=session_id)
    linked = sorted(
        {
            record.parent_session_id
            for record in store.records()
            if record.session_id == session_id and record.parent_session_id
        }
    )
    findings = [
        {
            "seq": note.seq,
            "at": note.at.isoformat(),
            "tag": note.tag,
            "session_purged": note.session_purged,
            "note": note.note,
        }
        for note in operator_notes(store, session_id=session_id)
    ]

    verify_json = {
        "scope": f"session:{session_id}",
        "intact": chain_status.ok,
        "checked": chain_status.checked,
        "broken_at": chain_status.broken_at,
        "tombstones": coverage["tombstones"],
        "purges": coverage["purges"],
        "gaps": coverage["gaps"],
        "linked_sessions": linked,
    }
    verify_txt = "\n".join(
        [
            f"scope: session:{session_id}",
            f"intact: {chain_status.ok}",
            f"checked: {chain_status.checked}",
            f"broken_at: {chain_status.broken_at}",
            f"tombstones: {coverage['tombstones']}",
            f"purges: {coverage['purges']}",
            f"gaps: {coverage['gaps']}",
            "forensic note: this bundle shows exactly what it verified, no more.",
        ]
    )

    members: dict[str, bytes] = {
        "records.ndjson": _ndjson_bytes(rows),
        "FORENSIC_SOUNDNESS.md": statement().encode("utf-8"),
        "chain.json": _json_bytes(
            {
                "segment": rows,
                "checkpoints": _nearest_checkpoints(store, [row["seq"] for row in rows]),
            }
        ),
        "verify.json": _json_bytes(verify_json),
        "verify.txt": (verify_txt + "\n").encode("utf-8"),
        "signing.json": _json_bytes(signing_status(store, Path(store_path).parent).to_dict()),
        "privacy.json": _json_bytes(
            {
                "leak_free": privacy.passed,
                "checks": privacy.checks,
                "leaks": list(privacy.leaks),
                "quarantine_present": privacy.quarantine_present,
            }
        ),
        "coverage.json": _json_bytes(coverage),
        "inventory.json": _json_bytes(inventory_to_json(inventory)),
        "findings.json": _json_bytes(findings),
        "denials.json": _json_bytes(
            {
                "sequences": [
                    {
                        "denied_tool": sequence.denied_tool,
                        "denied_at": sequence.denied_at.isoformat(),
                        "reason": sequence.reason,
                        "follow_ups": [
                            {"tool": f.tool, "outcome": f.outcome, "at": f.at.isoformat()}
                            for f in sequence.follow_ups
                        ],
                    }
                    for sequence in denial_sequences(
                        [entry.record for entry in entries if entry.record is not None]
                    )
                ]
            }
        ),
    }
    for include in includes:
        if include == INCIDENT_REPORT_FILENAME:
            members[include] = _json_bytes(build_incident_report(store, session_id, now=moment))
        else:
            raise ValueError(f"unknown include {include!r}")
    if include_bom:
        members["bom.cdx.json"] = _json_bytes(to_cyclonedx(build_bom(store, session_id=session_id)))
    schema_dir = _schema_dir()
    if schema_dir is not None:
        for name in ("agent-record.schema.json", "security-event.schema.json"):
            schema_path = schema_dir / name
            if schema_path.is_file():
                members[f"SCHEMA/{name}"] = schema_path.read_bytes()

    summary = _summary(session_id, moment, rows, verify_json, members, findings)
    members["summary.md"] = summary.encode("utf-8")

    schema_ids = [
        "https://github.com/agentsec-ecosystem/agentwatch/schema/agent-record.schema.json",
        "https://github.com/agentsec-ecosystem/agentwatch/schema/security-event.schema.json",
    ]
    manifest = {
        "bundle_format": BUNDLE_FORMAT,
        "bundle_format_version": BUNDLE_FORMAT_VERSION,
        "created_at": moment.isoformat(),
        "tool_version": _tool_version(),
        "store_format_version": store.format,
        "schema_ids": schema_ids,
        "session_id": session_id,
        "members": {name: _sha256(data) for name, data in members.items()},
    }
    members["manifest.json"] = _json_bytes(manifest)
    return EvidenceBundle(session_id=session_id, members=members)


def _summary(
    session_id: str,
    moment: datetime,
    rows: list[dict[str, Any]],
    verify: dict[str, Any],
    members: dict[str, bytes],
    findings: list[dict[str, Any]],
) -> str:
    lines = [
        f"# Evidence bundle — session {session_id}",
        "",
        f"- created: {moment.isoformat()}",
        f"- records: {len(rows)}",
        f"- chain intact: {verify['intact']}",
        f"- complete: {verify['gaps'] == []}",
        "- leak-free: see privacy.json",
        f"- tombstones: {len(verify['tombstones'])}",
        f"- purges: {len(verify['purges'])}",
        "- handling: may contain redacted-but-sensitive paths/arguments; treat as confidential.",
        "",
        "## Findings",
        "",
    ]
    if findings:
        for finding in findings:
            tag = f" [{finding['tag']}]" if finding["tag"] else ""
            lines.append(f"- seq {finding['seq']}{tag} ({finding['at']}): {finding['note']}")
    else:
        lines.append("- none recorded")
    lines.extend(["", "## Members", ""])
    lines.extend(f"- `{name}`" for name in sorted(members))
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class BundleVerification:
    """The independent verdict on a bundle (offline, no store)."""

    bundle_format: str
    intact: bool
    complete: bool
    leak_free: bool
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.intact and not self.problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_format": self.bundle_format,
            "intact": self.intact,
            "complete": self.complete,
            "leak_free": self.leak_free,
            "problems": list(self.problems),
        }


def verify_bundle(path: Path | str) -> BundleVerification:
    """Re-verify a bundle offline: member hashes and the chain segment.

    Never raises for a bad bundle; returns the verdict with problems enumerated.
    """
    bundle_path = Path(path)
    problems: list[str] = []
    try:
        with zipfile.ZipFile(bundle_path) as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names:
                return BundleVerification("", False, False, False, ("manifest.json missing",))
            manifest = json.loads(archive.read("manifest.json"))
            bundle_format = str(manifest.get("bundle_format", ""))
            if bundle_format != BUNDLE_FORMAT:
                return BundleVerification(
                    bundle_format,
                    False,
                    False,
                    False,
                    (f"unknown bundle format version {bundle_format!r}",),
                )
            recorded: dict[str, str] = manifest.get("members", {})
            for name, digest in recorded.items():
                if name not in names:
                    problems.append(f"member missing: {name}")
                    continue
                if _sha256(archive.read(name)) != digest:
                    problems.append(f"member tampered: {name}")
            intact_segment = _verify_segment(archive.read("records.ndjson"), problems)
            complete = _read_bool(archive, "coverage.json", "complete", problems)
            leak_free = _read_bool(archive, "privacy.json", "leak_free", problems)
    except (zipfile.BadZipFile, OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        return BundleVerification("", False, False, False, (f"unreadable bundle: {exc}",))

    intact = intact_segment and not any("tampered" in p or "missing" in p for p in problems)
    return BundleVerification(
        bundle_format=bundle_format,
        intact=intact,
        complete=complete,
        leak_free=leak_free,
        problems=tuple(problems),
    )


def _verify_segment(data: bytes, problems: list[str]) -> bool:
    from agentwatch.session_export import verify_export

    rows: list[dict[str, Any]] = []
    for line in data.decode("utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    if not verify_export(rows):
        problems.append("chain segment failed verification")
        return False
    return True


def _read_bool(archive: zipfile.ZipFile, name: str, key: str, problems: list[str]) -> bool:
    try:
        payload = json.loads(archive.read(name))
    except (KeyError, json.JSONDecodeError):
        problems.append(f"{name} unreadable")
        return False
    return bool(payload.get(key, False))


__all__ = [
    "BUNDLE_FORMAT",
    "BUNDLE_FORMAT_VERSION",
    "BundleVerification",
    "EvidenceBundle",
    "build_bundle",
    "validate_record",
    "verify_bundle",
]
