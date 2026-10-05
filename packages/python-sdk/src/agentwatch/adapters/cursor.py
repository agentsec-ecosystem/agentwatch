"""Cursor native-hooks adapter (M25 CUR-2, #304).

Cursor ships ``hooks.json`` (project ``.cursor/hooks.json``, user
``~/.cursor/hooks.json``, org-level) that invoke an external program with JSON on
stdin across the full agent loop. The hook binary frames each payload as::

    {"phase": <hook_event_name>, "harness": "cursor", "event": {...}}

and this adapter normalizes that framed message into records.

Native hooks give fidelity the modeled shim lacked: ``beforeReadFile`` (file
reads) and ``afterAgentThought`` (reasoning). Blocking ``before*`` events are
recorded as **observations** and are **never answered** (monitor-only, R2) — this
module returns records only and carries no permission decision. The
IDE/CLI/remote environment (``ide``) is tagged in ``environment``. Cloud agents
(cursor.com/agents) lack ``sessionStart``/``beforeSubmitPrompt``/Tab/``workspaceOpen``
hooks, a declared gap (:data:`DOCUMENTED_GAPS`), never a silent one.

Redaction runs here, before a record leaves the adapter (DD-06): by default no
content is captured (metadata-only). See ``docs/design/harness-adapter-design.md``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, cast

from agentwatch.identity import apply_identity_privacy
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    CredentialClass,
    Outcome,
    Producer,
    ProducerKind,
    RecordPrivacyMode,
    SecurityEvent,
    SecurityEventType,
    StepType,
    ToolCall,
    _parse_iso,
)
from agentwatch.redact import PrivacyMode, RedactionConfig
from agentwatch.secrets import fingerprint_spans, redact_mapping
from agentwatch.trace_context import format_traceparent, parse_traceparent

HARNESS_ID = "cursor"

# Provenance tag for every record this adapter produces: native harness hooks.
HOOK_PRODUCER = Producer(kind=ProducerKind.HOOK, name=HARNESS_ID)

# The blocking ``before*`` hooks. We subscribe for telemetry but never answer
# them (monitor-only, R2); the daemon writes records and exits 0.
BLOCKING_EVENTS = frozenset(
    {
        "preToolUse",
        "beforeShellExecution",
        "beforeMCPExecution",
        "beforeFileEdit",
        "beforeReadFile",
        "beforeTabFileRead",
        "beforeSubmitPrompt",
    }
)

# Every native hook event this adapter normalizes.
CAPABILITIES = frozenset(
    {
        "sessionStart",
        "sessionEnd",
        "preToolUse",
        "postToolUse",
        "postToolUseFailure",
        "beforeShellExecution",
        "afterShellExecution",
        "beforeMCPExecution",
        "afterMCPExecution",
        "beforeFileEdit",
        "afterFileEdit",
        "beforeReadFile",
        "beforeTabFileRead",
        "afterTabFileEdit",
        "subagentStart",
        "subagentStop",
        "beforeSubmitPrompt",
        "preCompact",
        "afterAgentThought",
        "afterAgentResponse",
        "workspaceOpen",
    }
)

# Honest, declared gaps (R3) — never dropped silently. Cloud agents do not emit
# the sessionStart/beforeSubmitPrompt/Tab/workspace hooks (PRD 42 edge cases).
DOCUMENTED_GAPS = ("cloud-agent-hook-events",)

# Tool name used for a phase that does not derive one from the payload.
_TOOL_NAMES: dict[str, str] = {
    "beforeShellExecution": "Shell",
    "afterShellExecution": "Shell",
    "beforeFileEdit": "Edit",
    "afterFileEdit": "Edit",
    "beforeReadFile": "Read",
    "beforeTabFileRead": "TabRead",
    "afterTabFileEdit": "TabEdit",
    "subagentStart": "subagent",
    "subagentStop": "subagent",
    "beforeSubmitPrompt": "user-prompt",
    "afterAgentThought": "agent-thought",
    "afterAgentResponse": "agent-response",
    "preCompact": "context-compacted",
    "workspaceOpen": "workspace-open",
    "sessionStart": "session-start",
    "sessionEnd": "session-end",
}

_POST_EVENTS = frozenset(
    {
        "postToolUse",
        "postToolUseFailure",
        "afterShellExecution",
        "afterMCPExecution",
        "afterFileEdit",
        "afterTabFileEdit",
        "subagentStop",
    }
)

_SESSION_EVENTS = frozenset({"sessionStart", "sessionEnd"})
_REASON_EVENTS = frozenset({"afterAgentThought", "afterAgentResponse"})

_PRIVACY_MAP = {
    PrivacyMode.METADATA_ONLY: RecordPrivacyMode.METADATA_ONLY,
    PrivacyMode.TRUNCATED: RecordPrivacyMode.TRUNCATED,
    PrivacyMode.HASHED: RecordPrivacyMode.HASHED,
    PrivacyMode.FULL: RecordPrivacyMode.FULL,
}


class CursorAdapterError(ValueError):
    """Raised when a Cursor hook message cannot be normalized."""


def split_mcp_tool(name: str) -> tuple[str | None, str]:
    """Split an MCP tool id ``mcp__<server>__<tool>`` into ``(server, tool)``.

    Defensive: a non-MCP name, a malformed ``mcp__`` name, or an empty
    server/tool segment returns ``(None, name)`` so the raw name is preserved.
    """
    parts = name.split("__")
    if len(parts) >= 3 and parts[0] == "mcp" and parts[1] and "__".join(parts[2:]):
        return parts[1], "__".join(parts[2:])
    return None, name


def _optional_str(source: Mapping[str, Any] | None, key: str) -> str | None:
    if not isinstance(source, Mapping):
        return None
    value = source.get(key)
    return value if isinstance(value, str) and value else None


def _identity_from(value: Any) -> AgentIdentity:
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


def _identity_dimension(base: AgentIdentity, event: Mapping[str, Any]) -> AgentIdentity:
    """Add optional identity fields a hook may expose (absent stays absent)."""
    block = event.get("agent")
    block = block if isinstance(block, Mapping) else None
    principal = _optional_str(block, "principal") or _optional_str(event, "principal")
    workload_identity = _optional_str(block, "workload_identity") or _optional_str(
        event, "workload_identity"
    )
    raw_class = (block.get("credential_class") if block else None) or event.get(
        "credential_class"
    )
    credential_class: CredentialClass | None = None
    if isinstance(raw_class, str):
        try:
            credential_class = CredentialClass(raw_class)
        except ValueError:
            credential_class = None
    raw_chain = (block.get("delegation_chain") if block else None) or event.get(
        "delegation_chain"
    )
    delegation_chain: tuple[str, ...] | None = None
    if isinstance(raw_chain, list) and all(isinstance(entry, str) for entry in raw_chain):
        delegation_chain = tuple(raw_chain)
    if (
        principal is None
        and workload_identity is None
        and credential_class is None
        and delegation_chain is None
    ):
        return base
    return replace(
        base,
        workload_identity=workload_identity,
        credential_class=credential_class,
        principal=principal,
        delegation_chain=delegation_chain,
    )


def identity_for(
    event: Mapping[str, Any], *, redaction: RedactionConfig | None = None
) -> AgentIdentity:
    """Agent identity for an event: explicit ``agent`` first, else subagent ids.

    The principal-hashing policy is applied for the session's privacy mode
    (hashed by default); an absent identity stays ``unknown`` — never inferred.
    """
    if event.get("agent") is not None:
        base = _identity_from(event["agent"])
    else:
        agent_id = event.get("agent_id")
        agent_type = event.get("agent_type")
        if agent_id is not None or agent_type is not None:
            base = AgentIdentity(
                identity=str(agent_id if agent_id is not None else agent_type),
                name=str(agent_type) if agent_type is not None else None,
            )
        else:
            base = AgentIdentity(identity="unknown")
    mode = (
        _PRIVACY_MAP[redaction.mode] if redaction is not None else RecordPrivacyMode.METADATA_ONLY
    )
    return apply_identity_privacy(_identity_dimension(base, event), mode=mode)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return _parse_iso(value)
    except ValueError as exc:
        raise CursorAdapterError(f"invalid timestamp {value!r}") from exc


def _timestamp(event: Mapping[str, Any]) -> datetime:
    parsed = _parse_timestamp(event.get("timestamp"))
    return parsed if parsed is not None else datetime.now(timezone.utc)


def _started_at(event: Mapping[str, Any], moment: datetime) -> datetime:
    return _parse_timestamp(event.get("started_at")) or moment


def _call_id(event: Mapping[str, Any]) -> str | None:
    raw = event.get("call_id") or event.get("tool_use_id") or event.get("tool_call_id")
    return str(raw) if raw is not None else None


def _duration(event: Mapping[str, Any]) -> float | None:
    raw = event.get("duration_ms")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    return None


def _is_error(event: Mapping[str, Any], phase: str) -> bool:
    if phase == "postToolUseFailure":
        return True
    if event.get("error"):
        return True
    if event.get("is_error") is True or event.get("success") is False:
        return True
    exit_code = event.get("exit_code")
    return isinstance(exit_code, int) and not isinstance(exit_code, bool) and exit_code != 0


def _redact(value: Any, cfg: RedactionConfig) -> Any:
    if isinstance(value, str):
        return cfg.apply(value, allowed=True)
    if isinstance(value, Mapping):
        return {key: _redact(item, cfg) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, cfg) for item in value]
    return value


def _arguments(
    raw: Any, cfg: RedactionConfig | None, *, capture: bool
) -> tuple[dict[str, Any] | None, RecordPrivacyMode]:
    if not isinstance(raw, Mapping) or not capture:
        return None, RecordPrivacyMode.METADATA_ONLY
    if cfg is None or cfg.mode is PrivacyMode.METADATA_ONLY:
        return None, RecordPrivacyMode.METADATA_ONLY
    redacted = cast("dict[str, Any]", _redact(raw, cfg))
    return redacted, _PRIVACY_MAP[cfg.mode]


def _captured_text(
    raw: Any, cfg: RedactionConfig | None
) -> tuple[dict[str, Any] | None, RecordPrivacyMode]:
    if not isinstance(raw, str) or cfg is None or cfg.mode is PrivacyMode.METADATA_ONLY:
        return None, RecordPrivacyMode.METADATA_ONLY
    applied = cfg.apply(raw, allowed=cfg.capture_prompts)
    if applied is None:
        return None, RecordPrivacyMode.METADATA_ONLY
    return {"text": applied}, _PRIVACY_MAP[cfg.mode]


def _secret_evidence(kinds: tuple[str, ...], fingerprints: tuple[str, ...]) -> dict[str, Any]:
    evidence: dict[str, Any] = {"kinds": list(kinds)}
    if fingerprints:
        evidence["fingerprints"] = list(fingerprints)
    return evidence


def _secret_event(
    tool_name: str,
    kinds: tuple[str, ...],
    fingerprint: Callable[[str], str] | None,
    raw: Any,
    moment: datetime,
) -> SecurityEvent | None:
    if not kinds:
        return None
    fingerprints = fingerprint_spans(raw, fingerprint) if fingerprint is not None else ()
    return SecurityEvent(
        type=SecurityEventType.SECRET_DETECTED,
        emitted_at=moment,
        emitter="agentwatch",
        tool=tool_name,
        evidence=_secret_evidence(kinds, fingerprints),
    )


def _ide_environment(event: Mapping[str, Any]) -> dict[str, Any] | None:
    """Metadata-only IDE/CLI/remote tag (``cursor-cli``/``cursor-ide``/``cursor-remote``)."""
    ide = event.get("ide")
    return {"ide": ide} if isinstance(ide, str) and ide else None


def tool_name_for(phase: str, event: Mapping[str, Any]) -> tuple[str | None, str]:
    """Resolve ``(server, tool)`` for a tool-event phase."""
    if phase in ("preToolUse", "postToolUse", "postToolUseFailure", "beforeMCPExecution",
                 "afterMCPExecution"):
        raw = event.get("tool_name") or event.get("tool") or _TOOL_NAMES.get(phase, "tool")
    else:
        raw = _TOOL_NAMES[phase]
    return split_mcp_tool(str(raw))


def _base(
    *,
    phase: str,
    event: Mapping[str, Any],
    tool_name: str,
    session_id: str,
    trace_id: str,
    call_id: str | None,
    project: str | None,
    environment: dict[str, Any] | None,
    event_time: datetime,
    redaction: RedactionConfig | None,
    step_type: StepType | None,
    outcome: Outcome,
    started_at: datetime,
    ended_at: datetime | None = None,
    duration_ms: float | None = None,
    arguments: dict[str, Any] | None = None,
    privacy_mode: RecordPrivacyMode = RecordPrivacyMode.METADATA_ONLY,
    server: str | None = None,
    security_event: SecurityEvent | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id=session_id,
        agent=identity_for(event, redaction=redaction),
        tool=ToolCall(
            name=tool_name,
            server=server,
            arguments=arguments,
            privacy_mode=privacy_mode,
        ),
        outcome=outcome,
        started_at=started_at,
        harness=HARNESS_ID,
        producer=HOOK_PRODUCER,
        trace_id=trace_id,
        span_id=call_id,
        project=project,
        ended_at=ended_at,
        duration_ms=duration_ms,
        step_type=step_type,
        environment=environment,
        security_event=security_event,
    )


def _normalize_message(
    message: Mapping[str, Any],
    *,
    redaction: RedactionConfig | None = None,
    secret_fingerprint: Callable[[str], str] | None = None,
) -> list[AgentRecord]:
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
    session_id = str(event.get("session_id") or "unknown")
    call_id = _call_id(event)
    trace_id = str(event.get("trace_id") or session_id)
    project = event.get("cwd") if isinstance(event.get("cwd"), str) else None
    environment = _ide_environment(event)
    event_time = _timestamp(event)

    if phase in _SESSION_EVENTS:
        reason = event.get("reason") or event.get("source")
        arguments = {"reason": str(reason)} if reason is not None else None
        parent_session_id = None
        if str(reason) in ("resume", "fork"):
            raw_parent = event.get("parent_session_id") or event.get("source_session_id")
            parent_session_id = str(raw_parent) if raw_parent is not None else None
        record = _base(
            phase=phase,
            event=event,
            tool_name=_TOOL_NAMES[phase],
            session_id=session_id,
            trace_id=trace_id,
            call_id=call_id,
            project=project,
            environment=environment,
            event_time=event_time,
            redaction=redaction,
            step_type=None,
            outcome=Outcome.OK,
            started_at=event_time,
            arguments=arguments,
        )
        return [replace(record, parent_session_id=parent_session_id)]

    if phase == "workspaceOpen":
        return [
            _base(
                phase=phase,
                event=event,
                tool_name=_TOOL_NAMES[phase],
                session_id=session_id,
                trace_id=trace_id,
                call_id=call_id,
                project=project,
                environment=environment,
                event_time=event_time,
                redaction=redaction,
                step_type=None,
                outcome=Outcome.OK,
                started_at=event_time,
            )
        ]

    if phase == "preCompact":
        raw_trigger = event.get("trigger") or event.get("source")
        trigger = (
            raw_trigger
            if isinstance(raw_trigger, str) and raw_trigger in ("auto", "manual")
            else "unknown"
        )
        compact_args: dict[str, Any] = {"trigger": trigger}
        for key, alternatives in (
            ("tokens_before", ("tokens_before", "before_tokens")),
            ("tokens_after", ("tokens_after", "after_tokens")),
        ):
            for alt in alternatives:
                value = event.get(alt)
                if isinstance(value, int) and not isinstance(value, bool):
                    compact_args[key] = value
                    break
        return [
            _base(
                phase=phase,
                event=event,
                tool_name=_TOOL_NAMES[phase],
                session_id=session_id,
                trace_id=trace_id,
                call_id=call_id,
                project=project,
                environment=environment,
                event_time=event_time,
                redaction=redaction,
                step_type=StepType.OBSERVE,
                outcome=Outcome.OK,
                started_at=event_time,
                arguments=compact_args,
            )
        ]

    if phase == "beforeSubmitPrompt":
        raw_prompt = event.get("prompt")
        masked_prompt, prompt_kinds = redact_mapping(raw_prompt)
        security_event = _secret_event(
            "user-prompt", prompt_kinds, secret_fingerprint, raw_prompt, event_time
        )
        captured = None
        privacy_mode = RecordPrivacyMode.METADATA_ONLY
        if (
            isinstance(masked_prompt, str)
            and redaction is not None
            and redaction.mode is not PrivacyMode.METADATA_ONLY
            and redaction.capture_prompts
        ):
            applied = redaction.apply(masked_prompt, allowed=True)
            if applied is not None:
                captured = {"prompt": applied}
                privacy_mode = _PRIVACY_MAP[redaction.mode]
        return [
            _base(
                phase=phase,
                event=event,
                tool_name=_TOOL_NAMES[phase],
                session_id=session_id,
                trace_id=trace_id,
                call_id=call_id,
                project=project,
                environment=environment,
                event_time=event_time,
                redaction=redaction,
                step_type=StepType.REASON,
                outcome=Outcome.OK,
                started_at=event_time,
                arguments=captured,
                privacy_mode=privacy_mode,
                security_event=security_event,
            )
        ]

    if phase in _REASON_EVENTS:
        raw = event.get("thought") if phase == "afterAgentThought" else event.get("response")
        masked, kinds = redact_mapping(raw)
        security_event = _secret_event(
            _TOOL_NAMES[phase], kinds, secret_fingerprint, raw, event_time
        )
        captured, privacy_mode = _captured_text(masked, redaction)
        return [
            _base(
                phase=phase,
                event=event,
                tool_name=_TOOL_NAMES[phase],
                session_id=session_id,
                trace_id=trace_id,
                call_id=call_id,
                project=project,
                environment=environment,
                event_time=event_time,
                redaction=redaction,
                step_type=StepType.REASON,
                outcome=Outcome.OK,
                started_at=event_time,
                arguments=captured,
                privacy_mode=privacy_mode,
                security_event=security_event,
            )
        ]

    # Tool-ish events: pre/postToolUse(+Failure), shell/MCP/file/subagent.
    server, tool_name = tool_name_for(phase, event)
    after = phase in _POST_EVENTS
    started_at = _started_at(event, event_time) if after else event_time
    ended_at = event_time if after else None
    duration_ms = _duration(event) if after else None
    outcome = Outcome.ERROR if _is_error(event, phase) else Outcome.OK
    step_type = (
        StepType.OBSERVE
        if after or phase in ("beforeReadFile", "beforeTabFileRead")
        else StepType.ACT
    )

    raw_input = event.get("tool_input")
    if raw_input is None:
        raw_input = event.get("input")
    if raw_input is None and phase in ("beforeShellExecution", "afterShellExecution"):
        raw_input = event.get("command")
    if raw_input is None:
        raw_input = event.get("file")
    masked_input, input_kinds = redact_mapping(raw_input)
    raw_response = event.get("tool_response") or event.get("response") or event.get("output")
    masked_response, response_kinds = redact_mapping(raw_response)
    secret_kinds = tuple(dict.fromkeys([*input_kinds, *response_kinds]))
    security_event = _secret_event(
        tool_name,
        secret_kinds,
        secret_fingerprint,
        raw_input if input_kinds else raw_response,
        event_time,
    )
    arguments, privacy_mode = _arguments(
        masked_input, redaction, capture=redaction is not None and redaction.capture_tool_args
    )
    captured_response, response_mode = _arguments(
        masked_response, redaction, capture=redaction is not None and redaction.capture_tool_args
    )

    tool = ToolCall(
        name=tool_name,
        server=server,
        arguments=arguments,
        response=captured_response,
        privacy_mode=(
            response_mode
            if privacy_mode is RecordPrivacyMode.METADATA_ONLY
            else privacy_mode
        ),
    )
    return [
        AgentRecord(
            session_id=session_id,
            agent=identity_for(event, redaction=redaction),
            tool=tool,
            outcome=outcome,
            started_at=started_at,
            harness=HARNESS_ID,
            producer=HOOK_PRODUCER,
            trace_id=trace_id,
            span_id=call_id,
            project=project,
            ended_at=ended_at,
            duration_ms=duration_ms,
            step_type=step_type,
            environment=environment,
            security_event=security_event,
        )
    ]


def normalize(
    message: Mapping[str, Any],
    *,
    redaction: RedactionConfig | None = None,
    secret_fingerprint: Callable[[str], str] | None = None,
) -> list[AgentRecord]:
    """Normalize one framed Cursor hook message, propagating any ``traceparent``.

    A hook that reports a ``traceparent`` joins the caller's trace instead of
    starting a new one; a malformed header is ignored.
    """
    records = _normalize_message(
        message, redaction=redaction, secret_fingerprint=secret_fingerprint
    )
    if not isinstance(message, Mapping):
        return records
    event = message.get("event")
    if not isinstance(event, Mapping):
        return records
    return [_with_traceparent(record, event) for record in records]


def _with_traceparent(record: AgentRecord, event: Mapping[str, Any]) -> AgentRecord:
    raw = event.get("traceparent")
    if not isinstance(raw, str):
        return record
    context = parse_traceparent(raw)
    if context is None:
        return record
    return replace(
        record,
        trace_id=context.trace_id,
        span_id=record.span_id or context.span_id,
        traceparent=format_traceparent(
            context.trace_id, context.span_id, sampled=context.sampled
        ),
    )
