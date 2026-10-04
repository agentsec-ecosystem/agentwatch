"""Modeled CrewAI adapter (M10 10.6, provisional Tier-2).

No CrewAI native event surface is documented in-repo, so this maps an **assumed**
shape (``{"phase": …, "event": {…}}``) to records. It is provisional: replace the
fixtures with real captures (M14/N4) before claiming full-fidelity support.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agentwatch.adapters.modeled import record_from_event
from agentwatch.records import AgentRecord, Outcome, StepType

HARNESS_ID = "crewai"
CAPABILITIES = frozenset({"agent_start", "agent_end", "task_start", "task_end", "tool_usage"})
DOCUMENTED_GAPS = ("mcp-server-events", "crew-memory", "delegation")

_DEFAULT_TOOL = {
    "agent_start": "Agent",
    "agent_end": "Agent",
    "task_start": "Task",
    "task_end": "Task",
    "tool_usage": "Tool",
}
_AFTER = frozenset({"agent_end", "task_end", "tool_usage"})


class CrewAiAdapterError(ValueError):
    """Raised when a modeled CrewAI event cannot be normalized."""


def normalize(message: Mapping[str, Any]) -> list[AgentRecord]:
    """Map one modeled CrewAI event to a record (or raise)."""
    if not isinstance(message, Mapping):
        raise CrewAiAdapterError("hook message must be an object")

    phase = message.get("phase")
    if phase not in CAPABILITIES:
        raise CrewAiAdapterError(
            f"unsupported phase {phase!r}; declared gaps: {', '.join(DOCUMENTED_GAPS)}"
        )
    event = message.get("event")
    if not isinstance(event, Mapping):
        raise CrewAiAdapterError("hook message is missing an 'event' object")

    phase = str(phase)
    after = phase in _AFTER
    session_id = str(event.get("session_id") or "unknown")
    tool_name = str(event.get("tool") or _DEFAULT_TOOL[phase])
    outcome = Outcome.ERROR if after and event.get("error") else Outcome.OK
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
