"""Modeled Gemini CLI adapter (M10 #82, provisional).

No Gemini CLI event surface is documented in-repo, so this maps an **assumed**
shape to records. It is provisional: replace the fixtures with real captures
(M14/N4) before claiming full-fidelity support.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agentwatch.adapters.modeled import record_from_event
from agentwatch.records import AgentRecord, Outcome, StepType

HARNESS_ID = "gemini-cli"
CAPABILITIES = frozenset({"tool_call", "tool_result", "session_start", "session_end"})
DOCUMENTED_GAPS = ("mcp-server-events",)


class GeminiCliAdapterError(ValueError):
    """Raised when a modeled Gemini CLI event cannot be normalized."""


def normalize(message: Mapping[str, Any]) -> list[AgentRecord]:
    """Map one modeled Gemini CLI event to a record (or raise)."""
    if not isinstance(message, Mapping):
        raise GeminiCliAdapterError("event message must be an object")

    phase = message.get("phase")
    if phase not in CAPABILITIES:
        raise GeminiCliAdapterError(
            f"unsupported phase {phase!r}; declared gaps: {', '.join(DOCUMENTED_GAPS)}"
        )
    event = message.get("event")
    if not isinstance(event, Mapping):
        raise GeminiCliAdapterError("event message is missing an 'event' object")

    phase = str(phase)
    session_id = str(event.get("session_id") or "unknown")
    if phase in ("session_start", "session_end"):
        return [
            record_from_event(
                HARNESS_ID,
                session_id=session_id,
                tool_name=phase,
                step_type=None,
                outcome=Outcome.OK,
                event=event,
            )
        ]

    tool_name = str(event.get("tool") or "tool")
    if phase == "tool_call":
        step_type, outcome, ended = StepType.ACT, Outcome.OK, False
    else:  # tool_result
        failed = bool(event.get("is_error")) or bool(event.get("error"))
        step_type, outcome, ended = StepType.OBSERVE, Outcome.ERROR if failed else Outcome.OK, True
    return [
        record_from_event(
            HARNESS_ID,
            session_id=session_id,
            tool_name=tool_name,
            step_type=step_type,
            outcome=outcome,
            event=event,
            ended=ended,
        )
    ]
