"""Replay-as-code: deterministic session export with its chain segment (M13 J2, #204).

Exports one session's records as schema-stable NDJSON, each line carrying the
store's chain envelope (``seq``/``prev_hash``/``hash``) so an external consumer
(agentdrill, CI) can both read the records and independently verify the chain
segment. No egress; read-only on the store.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentwatch.records import validate_record
from agentwatch.store import RecordStore

EXPORT_SCHEMA = "agentwatch-session-export/1"


def _canonical(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _entry_hash(prev_hash: str, record: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + _canonical(record)).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SessionExport:
    """A session's export rows plus a summary."""

    session_id: str
    schema: str
    rows: tuple[dict[str, Any], ...]

    @property
    def count(self) -> int:
        return len(self.rows)


def export_session(store: RecordStore, session_id: str) -> SessionExport:
    """Collect one session's records with their chain envelopes (seq order)."""
    rows: list[dict[str, Any]] = []
    for entry in store.entries():
        record = entry.record
        if record is None or record.session_id != session_id:
            continue
        rows.append(
            {
                "record": record.to_dict(),
                "seq": entry.seq,
                "prev_hash": entry.prev_hash,
                "hash": entry.hash,
            }
        )
    return SessionExport(session_id=session_id, schema=EXPORT_SCHEMA, rows=tuple(rows))


def to_ndjson(export: SessionExport) -> str:
    """Render an export as deterministic NDJSON (one JSON object per line)."""
    lines = [
        json.dumps({"schema": export.schema, "session_id": export.session_id}, sort_keys=True),
    ]
    lines.extend(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in export.rows)
    return "\n".join(lines) + "\n"


def write_ndjson(export: SessionExport, path: Path) -> None:
    """Write an export to ``path`` atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(to_ndjson(export), encoding="utf-8")
    tmp.replace(path)


def parse_ndjson(text: str) -> SessionExport:
    """Parse an exported NDJSON document back into a :class:`SessionExport`."""
    records: list[dict[str, Any]] = []
    session_id = ""
    schema = EXPORT_SCHEMA
    for line in text.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            # A line that is valid JSON but not an object is malformed for this
            # format: fail closed with a controlled ValueError (never a TypeError).
            raise ValueError(f"export line is not a JSON object: {type(item).__name__}")
        if "record" not in item:
            session_id = str(item.get("session_id", session_id))
            schema = str(item.get("schema", schema))
            continue
        records.append(item)
    return SessionExport(session_id=session_id, schema=schema, rows=tuple(records))


def verify_export(rows: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> bool:
    """Reference consumer: validate every record and re-verify its chain hash.

    The export is a *sparse* chain segment — a session's records interleave with
    others in the store — so each row is verified against its own ``prev_hash``
    rather than the previous exported row. A tampered record fails.
    """
    for row in rows:
        record = row.get("record")
        if not isinstance(record, dict):
            return False
        try:
            validate_record(record)
        except ValueError:
            return False
        if _entry_hash(str(row.get("prev_hash")), record) != row.get("hash"):
            return False
    return True
