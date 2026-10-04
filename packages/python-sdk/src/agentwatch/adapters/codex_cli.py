"""Modeled Codex CLI adapter (M10 #81, provisional).

No Codex CLI event surface is documented in-repo, so this maps an **assumed**
shape to records. It is provisional: replace the fixtures with real captures
(M14/N4) before claiming full-fidelity support.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agentwatch.adapters.modeled import record_from_event
from agentwatch.records import AgentRecord, Outcome, StepType

HARNESS_ID = "codex-cli"
CAPABILITIES = frozenset({"exec_begin", "exec_end", "patch_apply"})
DOCUMENTED_GAPS = ("mcp-server-events",)

_TOOL = {"exec_begin": "shell", "exec_end": "shell", "patch_apply": "apply_patch"}


class CodexCliAdapterError(ValueError):
    """Raised when a modeled Codex CLI event cannot be normalized."""


def _nonzero_exit(event: Mapping[str, Any]) -> bool:
    code = event.get("exit_code")
    return isinstance(code, int) and not isinstance(code, bool) and code != 0


def normalize(message: Mapping[str, Any]) -> list[AgentRecord]:
    """Map one modeled Codex CLI event to a record (or raise)."""
    if not isinstance(message, Mapping):
        raise CodexCliAdapterError("event message must be an object")

    phase = message.get("phase")
    if phase not in CAPABILITIES:
        raise CodexCliAdapterError(
            f"unsupported phase {phase!r}; declared gaps: {', '.join(DOCUMENTED_GAPS)}"
        )
    event = message.get("event")
    if not isinstance(event, Mapping):
        raise CodexCliAdapterError("event message is missing an 'event' object")

    phase = str(phase)
    session_id = str(event.get("session_id") or "unknown")
    tool_name = str(event.get("tool") or _TOOL[phase])
    if phase == "exec_begin":
        step_type, outcome, ended = StepType.ACT, Outcome.OK, False
    elif phase == "exec_end":
        failed = bool(event.get("error")) or _nonzero_exit(event)
        step_type, outcome, ended = StepType.OBSERVE, Outcome.ERROR if failed else Outcome.OK, True
    else:  # patch_apply is atomic
        failed = event.get("success") is False or bool(event.get("error"))
        step_type, outcome, ended = StepType.ACT, Outcome.ERROR if failed else Outcome.OK, True
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
