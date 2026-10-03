"""Session replay: reconstruct an ordered action timeline (M5 5.2/5.6, R8).

Replay reads the local store (the source of truth), selects one session, and
returns its records in temporal order. It is a pure read: it never mutates the
store and never re-reads raw transcripts.

Resumed/forked sessions (M9, PRD 25 I3) link to a parent via
``parent_session_id`` on their boundary record; replay walks that chain so one
logical conversation replays as one timeline. A visited set guards cycles.
"""

from __future__ import annotations

from agentwatch.records import AgentRecord
from agentwatch.store import ChainEntry, RecordStore


def _session_entries(store: RecordStore, session_id: str) -> list[ChainEntry]:
    entries = [
        entry
        for entry in store.entries()
        if entry.record is not None and entry.record.session_id == session_id
    ]
    entries.sort(key=lambda entry: (entry.record.started_at, entry.seq))  # type: ignore[union-attr]
    return entries


def _parent_session(store: RecordStore, session_id: str) -> str | None:
    for entry in store.entries():
        record = entry.record
        if record is not None and record.session_id == session_id and record.parent_session_id:
            return record.parent_session_id
    return None


def replay_session(
    store: RecordStore, session_id: str, *, follow_parents: bool = True
) -> list[AgentRecord]:
    """Return a session's records, oldest-first, following parent links.

    When ``follow_parents`` is true (default), a resumed/forked session's parent
    chain is replayed first; a visited set stops on a cycle.
    """
    chain: list[str] = []
    seen: set[str] = set()
    current: str | None = session_id
    while current is not None and current not in seen:
        seen.add(current)
        chain.append(current)
        current = _parent_session(store, current) if follow_parents else None

    records: list[AgentRecord] = []
    for chain_id in reversed(chain):
        records.extend(
            entry.record for entry in _session_entries(store, chain_id) if entry.record is not None
        )
    return records
