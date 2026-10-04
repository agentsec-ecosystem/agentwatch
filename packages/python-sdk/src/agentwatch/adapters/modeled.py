"""Shared construction for modeled (provisional) harness adapters (M10).

Modeled adapters map an **assumed** native event shape to agentwatch records.
The shapes are provisional until real harness captures land (M14 field tests /
N4 version matrix); see `docs/plans/harness-adapters-plan.md`. Records are
metadata-only by default; secret detection runs before storage (DD-06).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    Producer,
    ProducerKind,
    SecurityEvent,
    SecurityEventType,
    StepType,
    ToolCall,
    _parse_iso,
)
from agentwatch.secrets import redact_mapping


def event_time(event: Mapping[str, Any]) -> datetime:
    """Event timestamp, or now when absent/malformed."""
    raw = event.get("timestamp")
    if isinstance(raw, str):
        try:
            return _parse_iso(raw)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _optional_time(value: Any) -> datetime | None:
    if isinstance(value, str):
        try:
            return _parse_iso(value)
        except ValueError:
            return None
    return None


def _duration(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def record_from_event(
    harness: str,
    *,
    session_id: str,
    tool_name: str,
    step_type: StepType | None,
    outcome: Outcome,
    event: Mapping[str, Any],
    server: str | None = None,
    ended: bool = False,
) -> AgentRecord:
    """Build a validated record from a modeled native event.

    Detects (never stores) secrets in the event, carries the event cwd as
    ``project``, and sets end/duration only for after-events.
    """
    moment = event_time(event)
    started = _optional_time(event.get("started_at")) or moment
    _, kinds = redact_mapping(event)
    security_event = (
        SecurityEvent(
            type=SecurityEventType.SECRET_DETECTED,
            emitted_at=moment,
            emitter="agentwatch",
            tool=tool_name,
            evidence={"kinds": list(kinds)},
        )
        if kinds
        else None
    )
    call_id = event.get("call_id")
    cwd = event.get("cwd")
    return AgentRecord(
        session_id=session_id,
        agent=AgentIdentity(identity=str(event.get("agent") or harness)),
        tool=ToolCall(name=tool_name, server=server),
        outcome=outcome,
        started_at=started,
        harness=harness,
        producer=Producer(kind=ProducerKind.SDK, name=harness),
        trace_id=str(event.get("trace_id") or session_id),
        span_id=str(call_id) if call_id is not None else None,
        project=cwd if isinstance(cwd, str) else None,
        ended_at=moment if ended else None,
        duration_ms=_duration(event.get("duration_ms")) if ended else None,
        step_type=step_type,
        security_event=security_event,
    )
