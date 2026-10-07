"""Permission mode as a time-varying fact (M29 APV-2, PRD 49).

The active permission mode is recorded on every call; every mode *transition* is
its own observation (``permission-mode-changed``), so a session that moves
``default -> bypass -> default`` reconstructs exactly, and the bypass interval can
be flagged. A call with no mode data is ``unknown`` — never inferred.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    PermissionMode,
    Producer,
    RecordPrivacyMode,
    ToolCall,
)

MODE_CHANGED_TOOL = "permission-mode-changed"


def is_permission_mode_change(record: AgentRecord) -> bool:
    """Whether a record is a mode-transition observation."""
    return record.tool.name == MODE_CHANGED_TOOL


def _args_mode(arguments: object, key: str) -> PermissionMode:
    if isinstance(arguments, dict):
        raw = arguments.get(key)
        if isinstance(raw, str):
            try:
                return PermissionMode(raw)
            except ValueError:
                return PermissionMode.UNKNOWN
    return PermissionMode.UNKNOWN


def transition_mode(record: AgentRecord) -> PermissionMode:
    """The mode a transition puts in force (the ``to`` mode)."""
    if record.permission_mode is not None:
        return record.permission_mode
    return _args_mode(record.tool.arguments, "to")


def permission_mode_change_record(
    *,
    session_id: str,
    at: datetime,
    from_mode: PermissionMode,
    to_mode: PermissionMode,
    harness: str | None = None,
    producer: Producer | None = None,
    agent: AgentIdentity | None = None,
    trace_id: str | None = None,
) -> AgentRecord:
    """Build a mode-transition observation (metadata only, no step type)."""
    return AgentRecord(
        session_id=session_id,
        agent=agent or AgentIdentity(identity="unknown"),
        tool=ToolCall(
            name=MODE_CHANGED_TOOL,
            arguments={"from": from_mode.value, "to": to_mode.value},
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
        outcome=Outcome.OK,
        started_at=at,
        harness=harness,
        producer=producer,
        trace_id=trace_id or session_id,
        step_type=None,
        permission_mode=to_mode,
    )


def _current_mode(record: AgentRecord, current: PermissionMode) -> PermissionMode:
    return record.permission_mode if record.permission_mode is not None else current


@dataclass(frozen=True)
class ModeInterval:
    """A contiguous run of calls under one permission mode."""

    mode: PermissionMode
    start: datetime
    end: datetime
    calls: int

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "calls": self.calls,
        }


def _ordered(records: Iterable[AgentRecord]) -> list[AgentRecord]:
    return sorted(records, key=lambda record: record.started_at)


def effective_modes(records: Iterable[AgentRecord]) -> dict[int, PermissionMode]:
    """Assign each record its effective mode, reconstructing across transitions.

    Records are keyed by :func:`id` (records are not hashable). A session is
    walked in time order; an explicit mode on a call wins, otherwise the most
    recent transition's mode applies. No data → ``unknown``.
    """
    modes: dict[int, PermissionMode] = {}
    current = PermissionMode.UNKNOWN
    for record in _ordered(records):
        if is_permission_mode_change(record):
            current = transition_mode(record)
            modes[id(record)] = current
            continue
        mode = _current_mode(record, current)
        modes[id(record)] = mode
        current = mode
    return modes


def mode_intervals(records: Iterable[AgentRecord]) -> tuple[ModeInterval, ...]:
    """Reconstruct contiguous ``(mode, start, end, calls)`` intervals per session."""
    by_session: dict[str, list[AgentRecord]] = {}
    for record in records:
        by_session.setdefault(record.session_id, []).append(record)
    intervals: list[ModeInterval] = []
    for session in sorted(by_session):
        current = PermissionMode.UNKNOWN
        open_mode: PermissionMode | None = None
        start: datetime | None = None
        end: datetime | None = None
        calls = 0

        def flush() -> None:
            nonlocal open_mode, start, end, calls
            if open_mode is not None and start is not None:
                intervals.append(ModeInterval(open_mode, start, end or start, calls))
            open_mode, start, end, calls = None, None, None, 0

        for record in _ordered(by_session[session]):
            if is_permission_mode_change(record):
                flush()
                current = transition_mode(record)
                continue
            mode = _current_mode(record, current)
            current = mode
            at = record.started_at
            if open_mode is None or mode is not open_mode:
                flush()
                open_mode, start, end, calls = mode, at, at, 1
            else:
                end = at
                calls += 1
        flush()
    return tuple(intervals)


def bypass_intervals(records: Iterable[AgentRecord]) -> tuple[ModeInterval, ...]:
    """The intervals under ``bypassPermissions`` (the incident question)."""
    return tuple(
        interval
        for interval in mode_intervals(records)
        if interval.mode is PermissionMode.BYPASS_PERMISSIONS
    )


__all__ = [
    "MODE_CHANGED_TOOL",
    "ModeInterval",
    "bypass_intervals",
    "effective_modes",
    "is_permission_mode_change",
    "mode_intervals",
    "permission_mode_change_record",
    "transition_mode",
]
