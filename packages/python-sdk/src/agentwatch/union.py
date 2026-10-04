"""Read-time union of SDK spans and harness records (M21 S11, PRD 37).

PRD 14 defers *write-time* SDK→store unification (two producers on one hash
chain) to v0.2.0 for good reason. The cheap 80% is a **read-time** union: expose
both producers behind one query with an explicit ``source: hook | sdk`` field.

No shared chain, no ordering, no invariant change. Only harness records are
chain-protected as-author; an SDK-sourced entry is read-only and is labelled
**not chain-protected** at every surface so it is never mistaken for
tamper-evident evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentwatch.records import AgentRecord, ProducerKind, effective_producer
from agentwatch.store import RecordStore

SOURCE_HOOK = "hook"
SOURCE_SDK = "sdk"


@dataclass(frozen=True)
class UnionRow:
    """One record tagged with its producer source and integrity class."""

    source: str
    chain_protected: bool
    record: AgentRecord

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "chain_protected": self.chain_protected,
            "record": self.record.to_dict(),
        }


def source_of(record: AgentRecord) -> str:
    """The producer source of a record: ``sdk`` or ``hook``.

    An SDK-produced span is ``sdk``; every other provenance (harness hook,
    import, ingest, proxy, event) is treated as harness-side ``hook`` for the
    union's purposes.
    """
    kind = effective_producer(record).kind
    return SOURCE_SDK if kind is ProducerKind.SDK else SOURCE_HOOK


def union_records(
    records: list[AgentRecord],
    *,
    source: str | None = None,
    session_id: str | None = None,
) -> list[UnionRow]:
    """Compose records from both sources, in store order, with ``source`` set."""
    rows: list[UnionRow] = []
    for record in records:
        record_source = source_of(record)
        if source is not None and record_source != source:
            continue
        if session_id is not None and record.session_id != session_id:
            continue
        # Only harness records are chain-protected as-author.
        rows.append(
            UnionRow(
                source=record_source,
                chain_protected=record_source == SOURCE_HOOK,
                record=record,
            )
        )
    return rows


def union(
    store: RecordStore, *, source: str | None = None, session_id: str | None = None
) -> list[UnionRow]:
    """Read-time union over the local store."""
    return union_records(store.records(), source=source, session_id=session_id)


def render_union(rows: list[UnionRow]) -> str:
    """Human readout; SDK entries are explicitly marked not chain-protected."""
    lines = ["agentwatch union — hook records + SDK spans (read-time, no shared chain)"]
    if not rows:
        lines.append("  (no records)")
        return "\n".join(lines)
    for row in rows:
        integrity = "chain-protected" if row.chain_protected else "NOT chain-protected"
        lines.append(
            f"  [{row.source}] {row.record.started_at.isoformat()} "
            f"{row.record.tool.name} ({integrity})"
        )
    if any(not row.chain_protected for row in rows):
        lines.append("  note: sdk entries are read-only and not chain-protected")
    return "\n".join(lines)


__all__ = [
    "SOURCE_HOOK",
    "SOURCE_SDK",
    "UnionRow",
    "render_union",
    "source_of",
    "union",
    "union_records",
]
