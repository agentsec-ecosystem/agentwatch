"""``agentwatch view``: a terminal timeline over the local store (M7 addition H4).

A read-only, zero-service view of recorded sessions: with no argument it lists
sessions; given a session id it prints the ordered action timeline. When stdout
is a TTY it pages interactively with stdlib curses; otherwise it prints plainly,
so it is scriptable and testable. No daemon, no network, no dependency (D-L).
"""

from __future__ import annotations

from agentwatch.replay import replay_session
from agentwatch.store import RecordStore
from agentwatch.tail import render_record


def list_sessions(store: RecordStore) -> list[str]:
    """Distinct session ids in first-seen order."""
    order: list[str] = []
    seen: set[str] = set()
    for record in store.records():
        if record.session_id not in seen:
            seen.add(record.session_id)
            order.append(record.session_id)
    return order


def render_session(store: RecordStore, session_id: str) -> str:
    """Render a session's ordered timeline, one line per record."""
    records = replay_session(store, session_id)
    return "\n".join(render_record(record) for record in records)
