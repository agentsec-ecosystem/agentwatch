"""Session replay: reconstruct an ordered action timeline (M5 5.2/5.6, R8).

Replay reads the local store (the source of truth), selects one session, and
returns its records in temporal order. It is a pure read: it never mutates the
store and never re-reads raw transcripts.

Resumed/forked sessions (M9, PRD 25 I3) link to a parent via
``parent_session_id`` on their boundary record; replay walks that chain so one
logical conversation replays as one timeline. A visited set guards cycles.

M16 S28: callers may pass a record set that already includes archived segments
(see :func:`agentwatch.archive.combined_records`) so replay reads across the
archive boundary.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from agentwatch.records import AgentRecord
from agentwatch.store import RecordStore


def replay_records(
    records: Sequence[AgentRecord], session_id: str, *, follow_parents: bool = True
) -> list[AgentRecord]:
    """Return a session's records from ``records``, oldest-first."""
    by_session: dict[str, list[AgentRecord]] = {}
    for record in records:
        by_session.setdefault(record.session_id, []).append(record)

    def parent_of(candidate: str) -> str | None:
        for record in by_session.get(candidate, ()):
            if record.parent_session_id:
                return record.parent_session_id
        return None

    chain: list[str] = []
    seen: set[str] = set()
    current: str | None = session_id
    while current is not None and current not in seen:
        seen.add(current)
        chain.append(current)
        current = parent_of(current) if follow_parents else None

    ordered: list[AgentRecord] = []
    for chain_id in reversed(chain):
        ordered.extend(sorted(by_session.get(chain_id, ()), key=lambda r: r.started_at))
    return ordered


def replay_session(
    store: RecordStore,
    session_id: str,
    *,
    follow_parents: bool = True,
    records: Iterable[AgentRecord] | None = None,
) -> list[AgentRecord]:
    """Return a session's records, oldest-first, following parent links."""
    source = list(records) if records is not None else store.records()
    return replay_records(source, session_id, follow_parents=follow_parents)
