"""Session end-reason vocabulary (M17 S33, PRD 33).

An aborted session looks identical to one that simply ended, so a human hitting
escape — the clearest labelled signal about agent quality — is lost. This derives
a distinct state from evidence already in the chain and keeps the honest default:
``abandoned`` (no end event) stays distinct from ``interrupted-by-user`` (explicit
stop), and an ambiguous reason becomes ``unknown`` rather than an inferred
interrupt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from agentwatch.records import AgentRecord
from agentwatch.store import RecordStore

COMPLETED = "completed"
INTERRUPTED = "interrupted-by-user"
ERRORED = "errored"
ABANDONED = "abandoned"
UNKNOWN = "unknown"

STATES = (COMPLETED, INTERRUPTED, ERRORED, ABANDONED, UNKNOWN)

_INTERRUPT_REASONS = frozenset(
    {
        "interrupt",
        "interrupted",
        "user-interrupt",
        "user_interrupt",
        "abort",
        "aborted",
        "cancel",
        "cancelled",
        "canceled",
        "escape",
        "user",
    }
)
_COMPLETED_REASONS = frozenset(
    {"clear", "logout", "prompt_input_exit", "exit", "completed", "end", "stop", "done"}
)
_UNKNOWN_REASONS = frozenset({"", "other", "unknown"})


@dataclass(frozen=True)
class SessionState:
    """The derived end state of one session."""

    session_id: str
    state: str
    ended_at: datetime | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "state": self.state,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "reason": self.reason,
        }


def _reason(record: AgentRecord) -> str | None:
    arguments = record.tool.arguments
    if arguments is None:
        return None
    value = arguments.get("reason")
    return value if isinstance(value, str) else None


def session_state(records: list[AgentRecord]) -> SessionState:
    """Derive a session's end state from its ordered records."""
    session_id = records[0].session_id if records else "unknown"
    end = next((record for record in reversed(records) if record.tool.name == "session-end"), None)
    reason = _reason(end) if end is not None else None
    normalized = (reason or "").strip().lower()

    if normalized in _INTERRUPT_REASONS:
        return SessionState(session_id, INTERRUPTED, end.started_at if end else None, reason)
    if end is None:
        return SessionState(session_id, ABANDONED, None, None)
    if any(record.outcome.value == "error" for record in records):
        return SessionState(session_id, ERRORED, end.started_at, reason)
    if normalized in _COMPLETED_REASONS:
        return SessionState(session_id, COMPLETED, end.started_at, reason)
    if normalized in _UNKNOWN_REASONS:
        return SessionState(session_id, UNKNOWN, end.started_at, reason)
    return SessionState(session_id, UNKNOWN, end.started_at, reason)


def session_states(store: RecordStore, sessions: list[str]) -> dict[str, SessionState]:
    """Derive the end state of several sessions from a store."""
    by_session: dict[str, list[AgentRecord]] = {session: [] for session in sessions}
    for record in store.records():
        if record.session_id in by_session:
            by_session[record.session_id].append(record)
    return {session: session_state(records) for session, records in by_session.items()}


__all__ = [
    "ABANDONED",
    "COMPLETED",
    "ERRORED",
    "INTERRUPTED",
    "STATES",
    "SessionState",
    "UNKNOWN",
    "session_state",
    "session_states",
]
