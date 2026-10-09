"""Modeled Gemini CLI adapter (M10 #82, provisional).

No Gemini CLI event surface is documented in-repo, so this maps an **assumed**
shape to records. It is provisional: replace the fixtures with real captures
(M14/N4) before claiming full-fidelity support.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from agentwatch.adapters.modeled import record_from_event
from agentwatch.identity import apply_identity_privacy
from agentwatch.records import (
    AgentRecord,
    Approval,
    Outcome,
    RecordPrivacyMode,
    StepType,
)

HARNESS_ID = "gemini-cli"
CAPABILITIES = frozenset({"tool_call", "tool_result", "session_start", "session_end"})
DOCUMENTED_GAPS = ("mcp-server-events",)

# Gemini's ``active_approval_mode`` is a harness-wide setting; a completed call
# under it is the authorization context. An unrecognized value stays honest
# ``unknown`` (never guessed).
_APPROVAL_MODES = {
    "auto": Approval.AUTO,
    "on-request": Approval.USER,
    "on_request": Approval.USER,
    "ask": Approval.USER,
    "never": Approval.DENIED,
    "none": Approval.DENIED,
    "deny": Approval.DENIED,
}


class GeminiCliAdapterError(ValueError):
    """Raised when a modeled Gemini CLI event cannot be normalized."""


def _map_native_attributes(record: AgentRecord, event: Mapping[str, Any]) -> AgentRecord:
    """Map Gemini's native OTel attributes onto the record (GEM-2).

    ``active_approval_mode`` → approval provenance (S14); ``user.email`` → a
    (hashed) on-behalf-of principal (IDN-1); ``installation.id`` → agent identity
    and ``session.id`` → session correlation.
    """
    updates: dict[str, Any] = {}
    mode = event.get("active_approval_mode")
    if isinstance(mode, str):
        updates["approval"] = _APPROVAL_MODES.get(mode.strip().lower(), Approval.UNKNOWN)
    session = event.get("session.id")
    if isinstance(session, str) and session:
        updates["session_id"] = session
        if record.trace_id == record.session_id:
            updates["trace_id"] = session

    agent = record.agent
    identity = event.get("installation.id")
    if isinstance(identity, str) and identity:
        agent = replace(agent, identity=identity)
    email = event.get("user.email") or event.get("user_email")
    if isinstance(email, str) and email:
        agent = apply_identity_privacy(
            replace(agent, principal=email), mode=RecordPrivacyMode.METADATA_ONLY
        )
    if agent is not record.agent:
        updates["agent"] = agent
    return replace(record, **updates) if updates else record


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
        records = [
            record_from_event(
                HARNESS_ID,
                session_id=session_id,
                tool_name=phase,
                step_type=None,
                outcome=Outcome.OK,
                event=event,
            )
        ]
    else:
        tool_name = str(event.get("tool") or "tool")
        if phase == "tool_call":
            step_type, outcome, ended = StepType.ACT, Outcome.OK, False
        else:  # tool_result
            failed = bool(event.get("is_error")) or bool(event.get("error"))
            step_type, outcome, ended = (
                StepType.OBSERVE,
                Outcome.ERROR if failed else Outcome.OK,
                True,
            )
        records = [
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
    return [_map_native_attributes(record, event) for record in records]
