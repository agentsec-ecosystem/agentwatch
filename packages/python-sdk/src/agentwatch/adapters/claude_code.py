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

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, cast

from agentwatch.identity import apply_identity_privacy
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Approval,
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

HARNESS_ID = "claude-code"

# Provenance tag for every record this adapter produces (M15 S26).
HOOK_PRODUCER = Producer(kind=ProducerKind.HOOK, name=HARNESS_ID)

# Capability classes this adapter implements; anything else is a documented gap.
CAPABILITIES = frozenset(
    {
        "pre-tool-use",
        "post-tool-use",
        "post-tool-use-failure",
        "session-boundaries",
        "permission-denied",
        "user-prompt",
        "approval-provenance",
        "context-compaction",
        "permission-prompt",
    }
)

# Honest, declared gaps (R3) — never dropped silently.
DOCUMENTED_GAPS = ("mcp-server-events",)

_PRIVACY_MAP = {
    PrivacyMode.METADATA_ONLY: RecordPrivacyMode.METADATA_ONLY,
    PrivacyMode.TRUNCATED: RecordPrivacyMode.TRUNCATED,
    PrivacyMode.HASHED: RecordPrivacyMode.HASHED,
    PrivacyMode.FULL: RecordPrivacyMode.FULL,
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
    raw: Any, cfg: RedactionConfig | None
) -> tuple[dict[str, Any] | None, RecordPrivacyMode]:
    if not isinstance(raw, Mapping):
        return None, RecordPrivacyMode.METADATA_ONLY
    if cfg is None or cfg.mode is PrivacyMode.METADATA_ONLY or not cfg.capture_tool_args:
        return None, RecordPrivacyMode.METADATA_ONLY
    redacted = cast("dict[str, Any]", _redact(raw, cfg))
    return redacted, _PRIVACY_MAP[cfg.mode]


def split_mcp_tool(name: str) -> tuple[str | None, str]:
    """Split an MCP tool id ``mcp__<server>__<tool>`` into ``(server, tool)``.

    Defensive: a non-MCP name, a malformed ``mcp__`` name, or an empty
    server/tool segment returns ``(None, name)`` so the raw name is preserved
    rather than a bogus server recorded (PRD 25 D1).
    """
    parts = name.split("__")
    if len(parts) >= 3 and parts[0] == "mcp" and parts[1] and "__".join(parts[2:]):
        return parts[1], "__".join(parts[2:])
    return None, name


def identity_from(value: Any) -> AgentIdentity:
    if isinstance(value, str):
        return AgentIdentity(identity=value, name=value)
    if isinstance(value, Mapping):
        identity = value.get("identity") or value.get("name") or "unknown"
        prompt_version = value.get("prompt_version")
        return AgentIdentity(
            identity=str(identity),
            name=value.get("name"),
            version=value.get("version"),
            prompt_version=str(prompt_version) if isinstance(prompt_version, str) else None,
        )
    return AgentIdentity(identity="unknown")


def _optional_str(source: Mapping[str, Any] | None, key: str) -> str | None:
    if not isinstance(source, Mapping):
        return None
    value = source.get(key)
    return value if isinstance(value, str) and value else None


def _identity_dimension(base: AgentIdentity, event: Mapping[str, Any]) -> AgentIdentity:
    """Add the IDN-1 dimension from optional hook fields (absent stays unknown).

    A hook may expose the on-behalf-of principal, workload identity, credential
    class, or delegation chain at the top level or inside its ``agent`` block.
    Anything not exposed stays absent — never inferred.
    """
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

    The IDN-1 dimension is attached from optional hook fields and the principal
    hashing policy is applied for the session's privacy mode (hashed by default).
    """
    if event.get("agent") is not None:
        base = identity_from(event["agent"])
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
    # The hook carries the CLAUDE.md fingerprint at the top level (PRD 25 D2);
    # an explicit agent mapping's prompt_version wins.
    if base.prompt_version is None and isinstance(event.get("prompt_version"), str):
        base = replace(base, prompt_version=event["prompt_version"])
    mode = (
        _PRIVACY_MAP[redaction.mode] if redaction is not None else RecordPrivacyMode.METADATA_ONLY
    )
    return apply_identity_privacy(_identity_dimension(base, event), mode=mode)


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


def usage_record(event: Mapping[str, Any], *, tokens: int, model: str | None) -> AgentRecord:
    """A session-usage record derived from a transcript (usage + model only)."""
    session_id = str(event.get("session_id") or "unknown")
    base = identity_for(event)
    agent = AgentIdentity(
        identity=base.identity,
        name=base.name,
        version=base.version,
        prompt_version=base.prompt_version,
        model_version=model if model is not None else base.model_version,
        tool_schema_version=base.tool_schema_version,
        workload_type=base.workload_type,
    )
    return AgentRecord(
        session_id=session_id,
        agent=agent,
        tool=ToolCall(name="session-usage"),
        outcome=Outcome.OK,
        started_at=_timestamp(event),
        harness=HARNESS_ID,
        producer=HOOK_PRODUCER,
        trace_id=str(event.get("trace_id") or session_id),
        tokens=tokens,
        step_type=StepType.OBSERVE,
    )


def _secret_evidence(kinds: tuple[str, ...], fingerprints: tuple[str, ...]) -> dict[str, Any]:
    evidence: dict[str, Any] = {"kinds": list(kinds)}
    if fingerprints:
        evidence["fingerprints"] = list(fingerprints)
    return evidence


_APPROVAL_VALUES = frozenset(member.value for member in Approval)
_AUTO_SOURCES = frozenset({"allowlist", "settings", "config", "auto"})


def derive_approval(
    phase: str, event: Mapping[str, Any], *, pending_permission: bool = False
) -> Approval:
    """Derive who authorized a call, defaulting to ``unknown`` — never guessed.

    Per-harness derivation (published in ``docs/design/approval-provenance.md``):

    * a native denial is ``denied``;
    * an explicit ``approval`` field from the harness is authoritative;
    * a matching ``Notification`` permission prompt (``pending_permission``) is
      ``user``;
    * an allow decision whose source is an allow-list/settings is ``auto``;
    * ``permission_required: false`` is ``not-required``;
    * anything else is ``unknown`` — we never infer consent from ``outcome=ok``.
    """
    if phase == "denied":
        return Approval.DENIED
    explicit = event.get("approval")
    if isinstance(explicit, str) and explicit in _APPROVAL_VALUES:
        return Approval(explicit)
    if pending_permission:
        return Approval.USER
    if event.get("permission_required") is False:
        return Approval.NOT_REQUIRED
    if event.get("permission_decision") == "allow":
        source = event.get("permission_source")
        if isinstance(source, str) and source in _AUTO_SOURCES:
            return Approval.AUTO
    return Approval.UNKNOWN


_ENV_STRINGS = {"harness": ("name", "version"), "os": ("system", "arch")}
_ENV_AGENTWATCH = ("version",)
_ENV_PRINCIPAL_INTS = ("uid", "pid", "ppid")
_ENV_PRINCIPAL_STRINGS = ("username", "hostname")


def sanitize_environment(raw: Any, *, include_principal: bool = True) -> dict[str, Any] | None:
    """Allow-list a session-start snapshot down to metadata-only fields.

    Only known keys survive; env-var values and unknown fields are dropped. The
    principal block is omitted when ``include_principal`` is false (M19 S29).
    """
    if not isinstance(raw, Mapping):
        return None
    clean: dict[str, Any] = {}
    vcs = raw.get("vcs")
    if isinstance(vcs, Mapping):
        vcs_clean: dict[str, Any] = {"vcs": str(vcs.get("vcs", "unavailable"))}
        for key in ("commit", "branch"):
            if isinstance(vcs.get(key), str):
                vcs_clean[key] = vcs[key]
        if isinstance(vcs.get("dirty"), bool):
            vcs_clean["dirty"] = vcs["dirty"]
        clean["vcs"] = vcs_clean
    for section, keys in _ENV_STRINGS.items():
        block = raw.get(section)
        if isinstance(block, Mapping):
            clean[section] = {
                key: str(block[key]) for key in keys if isinstance(block.get(key), str)
            }
    agentwatch = raw.get("agentwatch")
    if isinstance(agentwatch, Mapping):
        clean["agentwatch"] = {
            key: str(agentwatch[key])
            for key in _ENV_AGENTWATCH
            if isinstance(agentwatch.get(key), str)
        }
    if isinstance(raw.get("context"), str):
        clean["context"] = raw["context"]
    principal = raw.get("principal")
    if include_principal and isinstance(principal, Mapping):
        clean_principal: dict[str, Any] = {}
        for key in _ENV_PRINCIPAL_INTS:
            if isinstance(principal.get(key), int) and not isinstance(principal.get(key), bool):
                clean_principal[key] = principal[key]
        for key in _ENV_PRINCIPAL_STRINGS:
            if isinstance(principal.get(key), str):
                clean_principal[key] = principal[key]
        if isinstance(principal.get("tty"), bool):
            clean_principal["tty"] = principal["tty"]
        if isinstance(principal.get("context"), str):
            clean_principal["context"] = principal["context"]
        clean["principal"] = clean_principal
    return clean or None


def _host_from(environment: Mapping[str, Any] | None) -> str | None:
    if not environment:
        return None
    principal = environment.get("principal")
    if isinstance(principal, Mapping) and isinstance(principal.get("hostname"), str):
        return str(principal["hostname"])
    return None


def _normalize_message(
    message: Mapping[str, Any],
    *,
    redaction: RedactionConfig | None = None,
    secret_fingerprint: Callable[[str], str] | None = None,
    pending_permission: bool = False,
    include_principal: bool = True,
) -> list[AgentRecord]:
    """Normalize one hook message into a record (or raise).

    Args:
        message: the framed hook message (``phase`` + ``event``).
        redaction: how much tool-argument content to capture; ``None`` means
            metadata-only (no content).
        secret_fingerprint: a keyed fingerprint function for secret spans, or
            ``None`` to skip fingerprints.
        pending_permission: whether a permission prompt preceded this call, so
            the derivation can record ``approval=user``.
        include_principal: keep the OS-principal block of a session-start
            snapshot; ``False`` drops it (M19 S29).

    Raises:
        ClaudeCodeAdapterError: when the phase is unsupported or the event is
            missing (declared gaps are rejected explicitly, never dropped).
    """
    if not isinstance(message, Mapping):
        raise ClaudeCodeAdapterError("hook message must be an object")

    phase = message.get("phase")
    if phase not in (
        "pre",
        "post",
        "denied",
        "prompt",
        "notification",
        "compact",
        "session-start",
        "session-end",
    ):
        raise ClaudeCodeAdapterError(
            f"unsupported hook phase {phase!r}; expected 'pre', 'post', 'denied', 'prompt', "
            "'notification', 'compact', 'session-start', or 'session-end'"
        )

    event = message.get("event")
    if not isinstance(event, Mapping):
        raise ClaudeCodeAdapterError("hook message is missing an 'event' object")

    session_id = str(event.get("session_id") or "unknown")
    tool_name = str(event.get("tool_name") or event.get("tool") or "unknown")
    server, bare_tool_name = split_mcp_tool(tool_name)
    call_id = tool_call_id(event)
    trace_id = str(event.get("trace_id") or session_id)
    project = event.get("cwd") if isinstance(event.get("cwd"), str) else None
    approval = derive_approval(phase, event, pending_permission=pending_permission)
    # Only persist a decision we actually have; absence reads back as `unknown`
    # so a record never claims an authorization the harness did not expose.
    recorded_approval = approval if approval is not Approval.UNKNOWN else None
    environment = (
        sanitize_environment(event.get("environment"), include_principal=include_principal)
        if phase == "session-start"
        else None
    )
    host = _host_from(environment)
    # Mask secrets before any storage transform (DD-06); detection runs even when
    # content is not captured so a secret-detected event still fires (R5).
    masked_input, secret_kinds = redact_mapping(event.get("tool_input"))
    masked_response, response_kinds = redact_mapping(event.get("tool_response"))
    if response_kinds:
        secret_kinds = tuple(dict.fromkeys([*secret_kinds, *response_kinds]))
    secret_fingerprints: tuple[str, ...] = ()
    if secret_kinds and secret_fingerprint is not None:
        collected: list[str] = []
        for raw in (event.get("tool_input"), event.get("tool_response")):
            collected.extend(fingerprint_spans(raw, secret_fingerprint))
        secret_fingerprints = tuple(dict.fromkeys(collected))
    arguments, privacy_mode = _arguments(masked_input, redaction)
    captured_response: dict[str, Any] | None = None
    event_time = _timestamp(event)
    security_event = None
    if secret_kinds:
        security_event = SecurityEvent(
            type=SecurityEventType.SECRET_DETECTED,
            emitted_at=event_time,
            emitter="agentwatch",
            tool=tool_name,
            evidence=_secret_evidence(secret_kinds, secret_fingerprints),
        )

    if phase in ("session-start", "session-end"):
        # Session-boundary record (M5 A1): no step type, reason carried as an argument.
        reason = event.get("reason") or event.get("source")
        boundary_args = {"reason": str(reason)} if reason is not None else None
        parent_session_id = None
        if str(reason) in ("resume", "fork"):
            raw_parent = event.get("parent_session_id") or event.get("source_session_id")
            parent_session_id = str(raw_parent) if raw_parent is not None else None
        record = AgentRecord(
            session_id=session_id,
            agent=identity_for(event, redaction=redaction),
            tool=ToolCall(
                name=phase,
                arguments=boundary_args,
                privacy_mode=RecordPrivacyMode.METADATA_ONLY,
            ),
            outcome=Outcome.OK,
            started_at=event_time,
            harness=HARNESS_ID,
            producer=HOOK_PRODUCER,
            trace_id=trace_id,
            span_id=call_id,
            project=project,
            parent_session_id=parent_session_id,
            step_type=None,
            environment=environment,
            host=host,
            security_event=security_event,
        )
        return [record]

    if phase == "compact":
        # A context compaction boundary (M19 S15): metadata only, never payload.
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
        record = AgentRecord(
            session_id=session_id,
            agent=identity_for(event, redaction=redaction),
            tool=ToolCall(
                name="context-compacted",
                arguments=compact_args,
                privacy_mode=RecordPrivacyMode.METADATA_ONLY,
            ),
            outcome=Outcome.OK,
            started_at=event_time,
            harness=HARNESS_ID,
            producer=HOOK_PRODUCER,
            trace_id=trace_id,
            span_id=call_id,
            project=project,
            step_type=StepType.OBSERVE,
        )
        return [record]

    if phase == "notification":
        # A permission prompt fires here (M19 S14). It is observation only: the
        # daemon correlates it with the following PreToolUse to record approval.
        marker_args = {"tool": tool_name} if tool_name != "unknown" else None
        record = AgentRecord(
            session_id=session_id,
            agent=identity_for(event, redaction=redaction),
            tool=ToolCall(
                name="permission-prompt",
                arguments=marker_args,
                privacy_mode=RecordPrivacyMode.METADATA_ONLY,
            ),
            outcome=Outcome.OK,
            started_at=event_time,
            harness=HARNESS_ID,
            producer=HOOK_PRODUCER,
            trace_id=trace_id,
            span_id=call_id,
            project=project,
            step_type=None,
        )
        return [record]

    if phase == "denied":
        # A harness-native permission denial (M5 A2): record it and emit `denied`.
        reason = event.get("reason")
        denial = SecurityEvent(
            type=SecurityEventType.DENIED,
            emitted_at=event_time,
            emitter="claude-code",
            tool=tool_name,
            reason=str(reason) if reason is not None else None,
        )
        record = AgentRecord(
            session_id=session_id,
            agent=identity_for(event, redaction=redaction),
            tool=ToolCall(
                name=bare_tool_name, server=server, arguments=arguments, privacy_mode=privacy_mode
            ),
            outcome=Outcome.DENIED,
            started_at=event_time,
            harness=HARNESS_ID,
            producer=HOOK_PRODUCER,
            trace_id=trace_id,
            span_id=call_id,
            project=project,
            step_type=StepType.OBSERVE,
            approval=recorded_approval,
            security_event=denial,
        )
        return [record]

    if phase == "prompt":
        # A user prompt as the opening reason step of a turn (M5 A3).
        masked_prompt, prompt_kinds = redact_mapping(event.get("prompt"))
        if prompt_kinds:
            prompt_fingerprints: tuple[str, ...] = ()
            if secret_fingerprint is not None:
                prompt_fingerprints = fingerprint_spans(event.get("prompt"), secret_fingerprint)
            security_event = SecurityEvent(
                type=SecurityEventType.SECRET_DETECTED,
                emitted_at=event_time,
                emitter="agentwatch",
                tool="user-prompt",
                evidence=_secret_evidence(prompt_kinds, prompt_fingerprints),
            )
        prompt_args: dict[str, Any] | None = None
        prompt_mode = RecordPrivacyMode.METADATA_ONLY
        if (
            isinstance(masked_prompt, str)
            and redaction is not None
            and redaction.mode is not PrivacyMode.METADATA_ONLY
            and redaction.capture_prompts
        ):
            applied = redaction.apply(masked_prompt, allowed=True)
            if applied is not None:
                prompt_args = {"prompt": applied}
                prompt_mode = _PRIVACY_MAP[redaction.mode]
        record = AgentRecord(
            session_id=session_id,
            agent=identity_for(event, redaction=redaction),
            tool=ToolCall(name="user-prompt", arguments=prompt_args, privacy_mode=prompt_mode),
            outcome=Outcome.OK,
            started_at=event_time,
            harness=HARNESS_ID,
            producer=HOOK_PRODUCER,
            trace_id=trace_id,
            span_id=call_id,
            project=project,
            step_type=StepType.REASON,
            security_event=security_event,
        )
        return [record]

    if phase == "pre":
        outcome = Outcome.OK
        step_type = StepType.ACT
        started_at = event_time
        ended_at: datetime | None = None
        duration_ms: float | None = None
    else:
        raw_response = event.get("tool_response")
        is_error = bool(event.get("error")) or (
            isinstance(raw_response, Mapping) and bool(raw_response.get("is_error"))
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
        captured_response, _ = _arguments(masked_response, redaction)

    record = AgentRecord(
        session_id=session_id,
        agent=identity_for(event, redaction=redaction),
        tool=ToolCall(
            name=bare_tool_name,
            server=server,
            arguments=arguments,
            response=captured_response,
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
        approval=recorded_approval,
        security_event=security_event,
    )
    return [record]


def normalize(
    message: Mapping[str, Any],
    *,
    redaction: RedactionConfig | None = None,
    secret_fingerprint: Callable[[str], str] | None = None,
    pending_permission: bool = False,
    include_principal: bool = True,
) -> list[AgentRecord]:
    """Normalize one hook message, propagating any W3C ``traceparent`` (TRACE-1).

    A hook that reports a ``traceparent`` (e.g. a subagent fan-out or an MCP-proxy
    hop) joins the caller's trace instead of starting a new one. A malformed header
    is ignored — the record keeps its own trace id, never an invented correlation.
    """
    records = _normalize_message(
        message,
        redaction=redaction,
        secret_fingerprint=secret_fingerprint,
        pending_permission=pending_permission,
        include_principal=include_principal,
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
