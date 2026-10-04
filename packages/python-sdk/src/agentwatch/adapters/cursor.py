"""Modeled Cursor adapter (M10 #80, provisional).

No Cursor native event surface is documented in-repo, so this maps an **assumed**
shape (``{"phase": …, "event": {…}}``) to records. It is provisional: replace the
fixtures with real captures (M14/N4) before claiming full-fidelity support.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agentwatch.adapters.modeled import record_from_event
from agentwatch.records import AgentRecord, Outcome, StepType

HARNESS_ID = "cursor"
CAPABILITIES = frozenset(
    {"beforeShellExecution", "afterShellExecution", "beforeFileEdit", "afterFileEdit"}
)
DOCUMENTED_GAPS = ("mcp-server-events",)

_TOOL = {
    "beforeShellExecution": "Shell",
    "afterShellExecution": "Shell",
    "beforeFileEdit": "Edit",
    "afterFileEdit": "Edit",
}


class CursorAdapterError(ValueError):
    """Raised when a modeled Cursor event cannot be normalized."""


def normalize(message: Mapping[str, Any]) -> list[AgentRecord]:
    """Map one modeled Cursor event to a record (or raise)."""
    if not isinstance(message, Mapping):
        raise CursorAdapterError("hook message must be an object")

    phase = message.get("phase")
    if phase not in CAPABILITIES:
        raise CursorAdapterError(
            f"unsupported phase {phase!r}; declared gaps: {', '.join(DOCUMENTED_GAPS)}"
        )
    event = message.get("event")
    if not isinstance(event, Mapping):
        raise CursorAdapterError("hook message is missing an 'event' object")

    phase = str(phase)
    after = phase.startswith("after")
    session_id = str(event.get("session_id") or "unknown")
    tool_name = str(event.get("tool") or _TOOL[phase])
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
