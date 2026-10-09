"""Cursor native-hooks adapter (M25 CUR-2, #304; realigned to the Cursor contract).

Cursor ships ``hooks.json`` (project ``.cursor/hooks.json``, user
``~/.cursor/hooks.json``, org-level) that invoke an external program with JSON on
stdin across the full agent loop. The hook binary frames each payload as::

    {"phase": <hook_event_name>, "harness": "cursor", "event": {...}}

and this adapter normalizes that framed message into records. Field names follow
the published Cursor contract (``conversation_id``, ``generation_id``,
``hook_event_name``, ``cursor_version``, ``workspace_roots``, ``file_path``, …;
see ``tests/fixtures/cursor/golden/manifest.json`` for the cited sources).

Blocking ``before*``/permission hooks are recorded as **observations** and are
**never answered** (monitor-only, R2) — this module returns records only and
carries no permission decision. ``user_email`` becomes the hashed ``principal``
(IDN-1); the IDE/CLI/remote environment (``ide``) is tagged in ``environment``.
Cloud agents do not run ``sessionStart``/``sessionEnd``/MCP/Tab/``workspaceOpen``
hooks, a declared gap (:data:`DOCUMENTED_GAPS`), never a silent one.

Redaction runs here, before a record leaves the adapter (DD-06): by default no
content is captured (metadata-only). See ``docs/design/harness-adapter-design.md``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
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

# Permission/blocking hooks. We subscribe for telemetry but never answer them
# (monitor-only, R2); the daemon writes records and exits 0.
BLOCKING_EVENTS = frozenset(
    {
        "preToolUse",
        "beforeShellExecution",
        "beforeMCPExecution",
        "beforeReadFile",
        "beforeTabFileRead",
        "beforeSubmitPrompt",
        "subagentStart",
    }
)

# Every native hook event this adapter normalizes (Cursor docs "Hook events").
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
        "beforeReadFile",
        "afterFileEdit",
        "beforeTabFileRead",
        "afterTabFileEdit",
        "subagentStart",
        "subagentStop",
        "beforeSubmitPrompt",
        "preCompact",
        "stop",
        "afterAgentResponse",
        "afterAgentThought",
        "workspaceOpen",
    }
)

# Honest, declared gaps (R3) — never dropped silently. Cloud agents do not run
# sessionStart/sessionEnd, MCP, Tab, or workspaceOpen hooks (Cursor docs
# "Hooks not available in cloud agents").
DOCUMENTED_GAPS = ("cloud-agent-hook-events",)

# Tool name used for a phase that does not derive one from the payload.
_TOOL_NAMES: dict[str, str] = {
    "beforeShellExecution": "Shell",
    "afterShellExecution": "Shell",
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
    "stop": "agent-stop",
    "workspaceOpen": "workspace-open",
    "sessionStart": "session-start",
    "sessionEnd": "session-end",
}

_TOOL_EVENTS = frozenset(
    {
        "preToolUse",
        "postToolUse",
        "postToolUseFailure",
        "beforeShellExecution",
        "afterShellExecution",
        "beforeMCPExecution",
        "afterMCPExecution",
        "beforeReadFile",
        "afterFileEdit",
        "beforeTabFileRead",
        "afterTabFileEdit",
        "subagentStart",
        "subagentStop",
    }
)

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

# Fields whose content is scanned for secrets (never stored by default).
_CONTENT_FIELDS = (
    "command",
    "prompt",
    "tool_input",
    "tool_output",
    "tool_response",
    "output",
    "result_json",
    "content",
    "text",
    "summary",
    "edits",
)

_PRIVACY_MAP = {
    PrivacyMode.METADATA_ONLY: RecordPrivacyMode.METADATA_ONLY,
    PrivacyMode.TRUNCATED: RecordPrivacyMode.TRUNCATED,
    PrivacyMode.HASHED: RecordPrivacyMode.HASHED,
    PrivacyMode.FULL: RecordPrivacyMode.FULL,
}


class CursorAdapterError(ValueError):
    """Raised when a Cursor hook message cannot be normalized."""


def split_mcp_tool(name: str) -> tuple[str | None, str]:
    """Split an ``mcp__<server>__<tool>`` id into ``(server, tool)`` (defensive).

    Cursor's native MCP hooks carry the server separately (``mcp_server_name``);
    this helper covers tool names that arrive already namespaced.
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
    """Add optional identity fields the contract exposes (absent stays absent)."""
    block = event.get("agent")
    block = block if isinstance(block, Mapping) else None
    # Cursor exposes the authenticated user as ``user_email``; it is the
    # on-behalf-of principal and is hashed by default (IDN-1).
    principal = (
        _optional_str(block, "principal")
        or _optional_str(event, "principal")
        or _optional_str(event, "user_email")
    )
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
    return AgentIdentity(
        identity=base.identity,
        name=base.name,
        version=base.version,
        prompt_version=base.prompt_version,
        model_version=base.model_version,
        tool_schema_version=base.tool_schema_version,
        workload_type=base.workload_type,
        workload_identity=workload_identity,
        credential_class=credential_class,
        principal=principal,
        delegation_chain=delegation_chain,
    )


def identity_for(
    event: Mapping[str, Any], *, redaction: RedactionConfig | None = None
) -> AgentIdentity:
    """Agent identity for an event: subagent ids first, else the base identity.

    The principal-hashing policy is applied for the session's privacy mode
    (hashed by default); an absent identity stays ``unknown`` — never inferred.
    """
    if event.get("agent") is not None:
        base = _identity_from(event["agent"])
    else:
        agent_id = event.get("subagent_id") or event.get("agent_id")
        agent_type = event.get("subagent_type") or event.get("agent_type")
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
    """The framing time. Cursor payloads carry no timestamp; the hook adds one."""
    parsed = _parse_timestamp(event.get("timestamp"))
    return parsed if parsed is not None else datetime.now(timezone.utc)


def _started_at(event: Mapping[str, Any], moment: datetime) -> datetime:
    return _parse_timestamp(event.get("started_at")) or moment


def _session_id(event: Mapping[str, Any]) -> str:
    return str(event.get("session_id") or event.get("conversation_id") or "unknown")


def _call_id(event: Mapping[str, Any]) -> str | None:
    raw = (
        event.get("tool_use_id")
        or event.get("tool_call_id")
        or event.get("subagent_id")
        or event.get("call_id")
        or event.get("generation_id")
    )
    return str(raw) if raw is not None else None


def _project(event: Mapping[str, Any]) -> str | None:
    cwd = event.get("cwd")
    if isinstance(cwd, str) and cwd:
        return cwd
    roots = event.get("workspace_roots")
    if isinstance(roots, list) and roots and isinstance(roots[0], str):
        return roots[0]
    return None


def _duration(event: Mapping[str, Any]) -> float | None:
    for key in ("duration_ms", "duration"):
        raw = event.get(key)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return float(raw)
    return None


def _is_error(event: Mapping[str, Any], phase: str) -> bool:
    if phase == "postToolUseFailure":
        return True
    if event.get("error") or event.get("error_message"):
        return True
    if event.get("is_error") is True or event.get("success") is False:
        return True
    if event.get("failure_type") in ("error", "timeout", "permission_denied"):
        return True
    if event.get("status") in ("error", "aborted"):
        return True
    if event.get("reason") == "error":
        return True
    exit_code = event.get("exit_code")
    return isinstance(exit_code, int) and not isinstance(exit_code, bool) and exit_code != 0


def _cursor_version(event: Mapping[str, Any]) -> str | None:
    return _optional_str(event, "cursor_version")


def _producer_for(event: Mapping[str, Any]) -> Producer:
    version = _cursor_version(event)
    return Producer(kind=HOOK_PRODUCER.kind, name=HOOK_PRODUCER.name, version=version)


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
    if not capture or cfg is None or cfg.mode is PrivacyMode.METADATA_ONLY:
        return None, RecordPrivacyMode.METADATA_ONLY
    if isinstance(raw, Mapping):
        return cast("dict[str, Any]", _redact(raw, cfg)), _PRIVACY_MAP[cfg.mode]
    if isinstance(raw, str):
        applied = cfg.apply(raw, allowed=True)
        return ({"text": applied}, _PRIVACY_MAP[cfg.mode]) if applied is not None else (
            None,
            RecordPrivacyMode.METADATA_ONLY,
        )
    return None, RecordPrivacyMode.METADATA_ONLY


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


def _scan_secrets(
    event: Mapping[str, Any],
    tool_name: str,
    fingerprint: Callable[[str], str] | None,
    moment: datetime,
) -> SecurityEvent | None:
    kinds: list[str] = []
    raw_values: list[Any] = []
    for field in _CONTENT_FIELDS:
        value = event.get(field)
        if value is None:
            continue
        _, found = redact_mapping(value)
        if found:
            kinds.extend(found)
            raw_values.append(value)
    if not kinds:
        return None
    fingerprints: tuple[str, ...] = ()
    if fingerprint is not None:
        collected: list[str] = []
        for value in raw_values:
            collected.extend(fingerprint_spans(value, fingerprint))
        fingerprints = tuple(dict.fromkeys(collected))
    return SecurityEvent(
        type=SecurityEventType.SECRET_DETECTED,
        emitted_at=moment,
        emitter="agentwatch",
        tool=tool_name,
        evidence=_secret_evidence(tuple(dict.fromkeys(kinds)), fingerprints),
    )


def _ide_environment(event: Mapping[str, Any]) -> dict[str, Any] | None:
    """Metadata-only IDE/CLI/remote tag (``cursor-cli``/``cursor-ide``/``cursor-remote``)."""
    ide = event.get("ide")
    return {"ide": ide} if isinstance(ide, str) and ide else None


def tool_name_for(phase: str, event: Mapping[str, Any]) -> tuple[str | None, str]:
    """Resolve ``(server, tool)`` for a tool-event phase."""
    if phase in ("beforeMCPExecution", "afterMCPExecution"):
        server = _optional_str(event, "mcp_server_name")
        tool = event.get("tool_name") or "mcp"
        _, bare = split_mcp_tool(str(tool))
        return server, bare
    if phase in ("preToolUse", "postToolUse", "postToolUseFailure"):
        raw = event.get("tool_name") or _TOOL_NAMES.get(phase, "tool")
        return split_mcp_tool(str(raw))
    return None, _TOOL_NAMES[phase]


def _raw_arguments(phase: str, event: Mapping[str, Any]) -> Any:
    if phase in ("preToolUse", "postToolUse", "postToolUseFailure"):
        return event.get("tool_input")
    if phase in ("beforeShellExecution", "afterShellExecution"):
        command = event.get("command")
        return {"command": command} if isinstance(command, str) else None
    if phase in ("beforeMCPExecution", "afterMCPExecution"):
        return event.get("tool_input")
    if phase in ("beforeReadFile", "beforeTabFileRead", "afterFileEdit", "afterTabFileEdit"):
        return {"file_path": event.get("file_path")} if event.get("file_path") else None
    return None


def _raw_response(phase: str, event: Mapping[str, Any]) -> Any:
    for key in ("tool_output", "output", "result_json", "response"):
        if event.get(key) is not None:
            return event[key]
    return None


def _base(
    *,
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
        producer=_producer_for(event),
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
    session_id = _session_id(event)
    call_id = _call_id(event)
    trace_id = str(event.get("conversation_id") or event.get("trace_id") or session_id)
    project = _project(event)
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
            outcome=Outcome.ERROR if _is_error(event, phase) else Outcome.OK,
            started_at=event_time,
            ended_at=event_time if phase == "sessionEnd" else None,
            duration_ms=_duration(event) if phase == "sessionEnd" else None,
            arguments=arguments,
        )
        if parent_session_id is None:
            return [record]
        return [AgentRecord.from_dict({**record.to_dict(), "parent_session_id": parent_session_id})]

    if phase == "workspaceOpen":
        return [
            _base(
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

    if phase == "stop":
        status = event.get("status")
        return [
            _base(
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
                outcome=Outcome.ERROR if _is_error(event, phase) else Outcome.OK,
                started_at=event_time,
                ended_at=event_time,
                arguments={"status": str(status)} if isinstance(status, str) else None,
            )
        ]

    if phase == "preCompact":
        raw_trigger = event.get("trigger")
        trigger = (
            raw_trigger
            if isinstance(raw_trigger, str) and raw_trigger in ("auto", "manual")
            else "unknown"
        )
        compact_args: dict[str, Any] = {"trigger": trigger}
        for key in (
            "context_usage_percent",
            "context_tokens",
            "context_window_size",
            "message_count",
            "messages_to_compact",
        ):
            value = event.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                compact_args[key] = value
        return [
            _base(
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
        security_event = _scan_secrets(event, "user-prompt", secret_fingerprint, event_time)
        captured, privacy_mode = _captured_text(raw_prompt, redaction)
        return [
            _base(
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
        raw = event.get("text")
        security_event = _scan_secrets(
            event, _TOOL_NAMES[phase], secret_fingerprint, event_time
        )
        captured, privacy_mode = _captured_text(raw, redaction)
        return [
            _base(
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
                ended_at=event_time if phase == "afterAgentThought" else None,
                duration_ms=_duration(event) if phase == "afterAgentThought" else None,
                arguments=captured,
                privacy_mode=privacy_mode,
                security_event=security_event,
            )
        ]

    # Tool-ish events: pre/postToolUse(+Failure), shell/MCP/file/subagent/Tab.
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

    security_event = _scan_secrets(event, tool_name, secret_fingerprint, event_time)
    arguments, privacy_mode = _arguments(
        _raw_arguments(phase, event),
        redaction,
        capture=redaction is not None and redaction.capture_tool_args,
    )
    response, response_mode = _arguments(
        _raw_response(phase, event),
        redaction,
        capture=redaction is not None and redaction.capture_tool_args,
    )
    tool = ToolCall(
        name=tool_name,
        server=server,
        arguments=arguments,
        response=response,
        privacy_mode=response_mode if response is not None else privacy_mode,
    )
    return [
        AgentRecord(
            session_id=session_id,
            agent=identity_for(event, redaction=redaction),
            tool=tool,
            outcome=outcome,
            started_at=started_at,
            harness=HARNESS_ID,
            producer=_producer_for(event),
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

    A hook that reports a ``traceparent`` (e.g. a subagent fan-out or an MCP-proxy
    hop) joins the caller's trace instead of starting a new one; a malformed
    header is ignored.
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
    return AgentRecord.from_dict(
        {
            **record.to_dict(),
            "trace_id": context.trace_id,
            "span_id": record.span_id or context.span_id,
            "traceparent": format_traceparent(
                context.trace_id, context.span_id, sampled=context.sampled
            ),
        }
    )
