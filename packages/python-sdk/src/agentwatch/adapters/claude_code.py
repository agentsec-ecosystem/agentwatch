"""Claude Code adapter: Pre/PostToolUse hooks -> agentwatch records (M3).

The hook script forwards a message of the shape::

    {"phase": "pre"|"post", "harness": "claude-code", "event": {...}}

``PreToolUse`` yields an *intent* record (``step_type=act``, no end); ``PostToolUse``
yields an *outcome* record (``ok``/``error``, with end time and duration). The two
records share a ``span_id`` when the harness supplies a ``tool_use_id``.

Redaction runs here, before a record leaves the adapter (DD-06): by default no
argument content is captured (metadata-only). Pass a
:class:`~agentwatch.redact.RedactionConfig` to capture truncated or hashed
arguments.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, cast

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    StepType,
    ToolCall,
    _parse_iso,
)
from agentwatch.redact import PrivacyMode, RedactionConfig

HARNESS_ID = "claude-code"

# Capability classes this adapter implements; anything else is a documented gap.
CAPABILITIES = frozenset({"pre-tool-use", "post-tool-use", "post-tool-use-failure"})

# Honest, declared gaps (R3) — never dropped silently.
DOCUMENTED_GAPS = ("session-boundaries", "mcp-server-events")

_PRIVACY_MAP = {
    PrivacyMode.METADATA_ONLY: RecordPrivacyMode.METADATA_ONLY,
    PrivacyMode.TRUNCATED: RecordPrivacyMode.TRUNCATED,
    PrivacyMode.HASHED: RecordPrivacyMode.HASHED,
}


class ClaudeCodeAdapterError(ValueError):
    """Raised when a hook message cannot be normalized."""


def _redact(value: Any, cfg: RedactionConfig) -> Any:
    if isinstance(value, str):
        return cfg.apply(value, allowed=True)
    if isinstance(value, Mapping):
        return {key: _redact(item, cfg) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, cfg) for item in value]
    return value


def _arguments(
    event: Mapping[str, Any], cfg: RedactionConfig | None
) -> tuple[dict[str, Any] | None, RecordPrivacyMode]:
    raw = event.get("tool_input")
    if not isinstance(raw, Mapping):
        return None, RecordPrivacyMode.METADATA_ONLY
    if cfg is None or cfg.mode is PrivacyMode.METADATA_ONLY or not cfg.capture_tool_args:
        return None, RecordPrivacyMode.METADATA_ONLY
    redacted = cast("dict[str, Any]", _redact(raw, cfg))
    return redacted, _PRIVACY_MAP[cfg.mode]


def identity_from(value: Any) -> AgentIdentity:
    if isinstance(value, str):
        return AgentIdentity(identity=value, name=value)
    if isinstance(value, Mapping):
        identity = value.get("identity") or value.get("name") or "unknown"
        return AgentIdentity(
            identity=str(identity),
            name=value.get("name"),
            version=value.get("version"),
        )
    return AgentIdentity(identity="unknown")


def _parse_optional_timestamp(value: Any) -> datetime | None:
    """Parse an optional ISO timestamp, rejecting a malformed one explicitly."""
    if not isinstance(value, str):
        return None
    try:
        return _parse_iso(value)
    except ValueError as exc:
        raise ClaudeCodeAdapterError(f"invalid timestamp {value!r}") from exc


def _timestamp(event: Mapping[str, Any]) -> datetime:
    parsed = _parse_optional_timestamp(event.get("timestamp"))
    return parsed if parsed is not None else datetime.now(timezone.utc)


def tool_call_id(event: Mapping[str, Any]) -> str | None:
    raw = event.get("tool_use_id") or event.get("tool_call_id")
    return str(raw) if raw is not None else None


def normalize(
    message: Mapping[str, Any],
    *,
    redaction: RedactionConfig | None = None,
) -> list[AgentRecord]:
    """Normalize one hook message into a record (or raise).

    Args:
        message: the framed hook message (``phase`` + ``event``).
        redaction: how much tool-argument content to capture; ``None`` means
            metadata-only (no content).

    Raises:
        ClaudeCodeAdapterError: when the phase is unsupported or the event is
            missing (declared gaps are rejected explicitly, never dropped).
    """
    if not isinstance(message, Mapping):
        raise ClaudeCodeAdapterError("hook message must be an object")

    phase = message.get("phase")
    if phase not in ("pre", "post"):
        raise ClaudeCodeAdapterError(f"unsupported hook phase {phase!r}; expected 'pre' or 'post'")

    event = message.get("event")
    if not isinstance(event, Mapping):
        raise ClaudeCodeAdapterError("hook message is missing an 'event' object")

    session_id = str(event.get("session_id") or "unknown")
    tool_name = str(event.get("tool_name") or event.get("tool") or "unknown")
    call_id = tool_call_id(event)
    trace_id = str(event.get("trace_id") or session_id)
    arguments, privacy_mode = _arguments(event, redaction)
    event_time = _timestamp(event)

    if phase == "pre":
        outcome = Outcome.OK
        step_type = StepType.ACT
        started_at = event_time
        ended_at: datetime | None = None
        duration_ms: float | None = None
    else:
        response = event.get("tool_response")
        is_error = bool(event.get("error")) or (
            isinstance(response, Mapping) and bool(response.get("is_error"))
        )
        outcome = Outcome.ERROR if is_error else Outcome.OK
        step_type = StepType.OBSERVE
        started_at = _parse_optional_timestamp(event.get("started_at")) or event_time
        ended_at = event_time
        raw_duration = event.get("duration_ms")
        duration_ms = (
            float(raw_duration)
            if isinstance(raw_duration, (int, float)) and not isinstance(raw_duration, bool)
            else None
        )

    record = AgentRecord(
        session_id=session_id,
        agent=identity_from(event.get("agent")),
        tool=ToolCall(name=tool_name, arguments=arguments, privacy_mode=privacy_mode),
        outcome=outcome,
        started_at=started_at,
        harness=HARNESS_ID,
        trace_id=trace_id,
        span_id=call_id,
        ended_at=ended_at,
        duration_ms=duration_ms,
        step_type=step_type,
    )
    return [record]
