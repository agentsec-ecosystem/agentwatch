"""Session replay: reconstruct an ordered action timeline (M5 5.2/5.6, R8).

Replay reads the local store (the source of truth), selects one session, and
returns its records in temporal order. It is a pure read: it never mutates the
store and never re-reads raw transcripts.
"""

from __future__ import annotations

from agentwatch.records import AgentRecord
from agentwatch.store import RecordStore


def replay_session(store: RecordStore, session_id: str) -> list[AgentRecord]:
    """Return one session's records, ordered by start time then chain position."""
    entries = [
        entry
        for entry in store.entries()
        if entry.record is not None and entry.record.session_id == session_id
    ]
    entries.sort(key=lambda entry: (entry.record.started_at, entry.seq))  # type: ignore[union-attr]
    return [entry.record for entry in entries]  # type: ignore[misc]
