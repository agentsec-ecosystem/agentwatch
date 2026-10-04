"""Modeled PydanticAI adapter (M10 10.6, provisional Tier-2).

No PydanticAI native event surface is documented in-repo, so this maps an
**assumed** shape (``{"phase": …, "event": {…}}``) to records. It is provisional:
replace the fixtures with real captures (M14/N4) before claiming full-fidelity
support.

Note this is the *record* adapter (foreign event -> :class:`AgentRecord`); the
in-process instrumentation wrapper lives in :mod:`agentwatch.pydantic`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agentwatch.adapters.modeled import record_from_event
from agentwatch.records import AgentRecord, Outcome, StepType

HARNESS_ID = "pydantic-ai"
CAPABILITIES = frozenset({"agent_run_start", "agent_run_end", "tool_call", "tool_result"})
DOCUMENTED_GAPS = ("mcp-server-events", "stream-events")

_DEFAULT_TOOL = {
    "agent_run_start": "Agent",
    "agent_run_end": "Agent",
    "tool_call": "Tool",
    "tool_result": "Tool",
}
_AFTER = frozenset({"agent_run_end", "tool_result"})


class PydanticAiAdapterError(ValueError):
    """Raised when a modeled PydanticAI event cannot be normalized."""


def _is_error(event: Mapping[str, Any]) -> bool:
    return bool(event.get("error") or event.get("is_error"))


def normalize(message: Mapping[str, Any]) -> list[AgentRecord]:
    """Map one modeled PydanticAI event to a record (or raise)."""
    if not isinstance(message, Mapping):
        raise PydanticAiAdapterError("hook message must be an object")

    phase = message.get("phase")
    if phase not in CAPABILITIES:
        raise PydanticAiAdapterError(
            f"unsupported phase {phase!r}; declared gaps: {', '.join(DOCUMENTED_GAPS)}"
        )
    event = message.get("event")
    if not isinstance(event, Mapping):
        raise PydanticAiAdapterError("hook message is missing an 'event' object")

    phase = str(phase)
    after = phase in _AFTER
    session_id = str(event.get("session_id") or "unknown")
    tool_name = str(event.get("tool_name") or event.get("tool") or _DEFAULT_TOOL[phase])
    outcome = Outcome.ERROR if after and _is_error(event) else Outcome.OK
    return [
        record_from_event(
            HARNESS_ID,
            session_id=session_id,
            tool_name=tool_name,
            step_type=StepType.OBSERVE if after else StepType.ACT,
            outcome=outcome,
            event=event,
            ended=after,
        )
    ]
