"""MCP proxy adapter: interposition frames -> agentwatch records (M10 N1 #83).

The proxy emits one JSON-RPC message per frame::

    {"phase": "mcp", "harness": "mcp-proxy", "event": {
        "server": "github", "session_id": "s-1",
        "direction": "request" | "response",
        "tool_name": "issue_get",            # required on a response
        "rpc": { ...JSON-RPC 2.0 message... },
        "timestamp": "...", "cwd": "/repo"}}

A ``tools/call`` request yields an *intent* record (``step_type=act``); its
response yields an *outcome* record (``step_type=observe``, ``error`` on a
JSON-RPC error, sharing the request's ``span_id``). A ``resources/read``
request/response is recorded the same way, with the resource URI kept as
metadata in ``tool.arguments['uri']`` (so ``search --mcp-resource`` finds it);
a resource link in a tool result is recorded as a ``resources/link``
observation. Anything else — a declared gap, an unknown phase, an unresolvable
method — is rejected explicitly, never dropped (PRD 17).

Redaction runs here, before a record leaves the adapter (DD-06): by default no
argument/response content is captured (metadata-only). Pass a
:class:`~agentwatch.redact.RedactionConfig` to capture truncated or hashed
content. A detected secret always emits a ``secret-detected`` security event,
even when content is not captured (R5).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, cast

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
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
from agentwatch.secrets import redact_mapping

HARNESS_ID = "mcp-proxy"

# Interposed MCP traffic is proxy-produced (M15 S26).
PROXY_PRODUCER = Producer(kind=ProducerKind.PROXY, name=HARNESS_ID)

# Capability classes this adapter implements; anything else is a documented gap.
CAPABILITIES = frozenset({"mcp-tools", "mcp-resources"})

# Honest, declared gaps — never dropped silently (R3). ``tools/call`` and
# ``resources/read`` are recorded; prompts and sampling are relayed by the proxy
# but have no record-model representation yet.
DOCUMENTED_GAPS = ("mcp-prompts", "mcp-sampling")

_PRIVACY_MAP = {
    PrivacyMode.METADATA_ONLY: RecordPrivacyMode.METADATA_ONLY,
    PrivacyMode.TRUNCATED: RecordPrivacyMode.TRUNCATED,
    PrivacyMode.HASHED: RecordPrivacyMode.HASHED,
    PrivacyMode.FULL: RecordPrivacyMode.FULL,
}


class McpProxyAdapterError(ValueError):
    """Raised when a proxy frame cannot be normalized."""


def _redact(value: Any, cfg: RedactionConfig) -> Any:
    if isinstance(value, str):
        return cfg.apply(value, allowed=True)
    if isinstance(value, Mapping):
        return {key: _redact(item, cfg) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, cfg) for item in value]
    return value


def _capture(
    raw: Any, cfg: RedactionConfig | None
) -> tuple[dict[str, Any] | None, RecordPrivacyMode]:
    """Capture (redacted) content only when config allows and the value is a mapping."""
    if not isinstance(raw, Mapping):
        return None, RecordPrivacyMode.METADATA_ONLY
    if cfg is None or cfg.mode is PrivacyMode.METADATA_ONLY or not cfg.capture_tool_args:
        return None, RecordPrivacyMode.METADATA_ONLY
    redacted = cast("dict[str, Any]", _redact(raw, cfg))
    return redacted, _PRIVACY_MAP[cfg.mode]


def _event_time(event: Mapping[str, Any]) -> datetime:
    raw = event.get("timestamp")
    if not isinstance(raw, str):
        return datetime.now(timezone.utc)
    try:
        return _parse_iso(raw)
    except ValueError as exc:
        raise McpProxyAdapterError(f"invalid timestamp {raw!r}") from exc


def _span_id(server: str, event: Mapping[str, Any], rpc: Mapping[str, Any]) -> str | None:
    """Correlate a call. A proxy-assigned ``call_id`` wins; else the JSON-RPC id.

    A JSON-RPC id is only unique among *outstanding* requests, so a harness may
    reuse one across calls; the proxy assigns a ``call_id`` per call so the
    daemon's dedup key stays unique (no silently dropped record).
    """
    call_id = event.get("call_id")
    if isinstance(call_id, str) and call_id:
        return f"mcp:{server}:{call_id}"
    raw_id = rpc.get("id")
    if raw_id is None or isinstance(raw_id, bool):
        return None
    return f"mcp:{server}:{raw_id}"


def normalize(
    message: Mapping[str, Any],
    *,
    redaction: RedactionConfig | None = None,
) -> list[AgentRecord]:
    """Normalize one proxy frame into a record (or raise).

    Raises:
        McpProxyAdapterError: when the frame is not a valid ``tools/call``
            request/response or names an unsupported phase (declared gaps are
            rejected explicitly, never dropped).
    """
    if not isinstance(message, Mapping):
        raise McpProxyAdapterError("hook message must be an object")

    if message.get("phase") != "mcp":
        raise McpProxyAdapterError(f"unsupported phase {message.get('phase')!r}; expected 'mcp'")

    event = message.get("event")
    if not isinstance(event, Mapping):
        raise McpProxyAdapterError("hook message is missing an 'event' object")

    direction = event.get("direction")
    if direction not in ("request", "response"):
        raise McpProxyAdapterError(
            f"unsupported direction {direction!r}; expected 'request' or 'response'"
        )

    rpc = event.get("rpc")
    if not isinstance(rpc, Mapping):
        raise McpProxyAdapterError("event is missing an 'rpc' object")

    server = event.get("server")
    if not isinstance(server, str) or not server:
        raise McpProxyAdapterError("event is missing a 'server'")

    session_id = str(event.get("session_id") or "unknown")
    project = event.get("cwd") if isinstance(event.get("cwd"), str) else None
    event_time = _event_time(event)

    resource: str | None = None
    if direction == "request":
        method = rpc.get("method")
        params = rpc.get("params")
        if not isinstance(params, Mapping):
            raise McpProxyAdapterError(f"{method!r} is missing a 'params' object")
        if method == "tools/call":
            name = params.get("name")
            if not isinstance(name, str) or not name:
                raise McpProxyAdapterError("tools/call is missing a tool 'name'")
            tool_name = name
            source: Any = params.get("arguments")
        elif method == "resources/read":
            uri = params.get("uri")
            if not isinstance(uri, str) or not uri:
                raise McpProxyAdapterError("resources/read is missing a resource 'uri'")
            tool_name = "resources/read"
            resource = uri
            source = None
        else:
            raise McpProxyAdapterError(
                f"unsupported method {method!r}; expected 'tools/call' or 'resources/read'"
            )
        step_type: StepType | None = StepType.ACT
        outcome = Outcome.OK
        ended_at: datetime | None = None
    else:
        name = event.get("tool_name")
        if not isinstance(name, str) or not name:
            raise McpProxyAdapterError("response is missing a 'tool_name'")
        tool_name = name
        raw_resource = event.get("resource")
        resource = raw_resource if isinstance(raw_resource, str) and raw_resource else None
        error = rpc.get("error")
        if error is not None:
            outcome = Outcome.ERROR
            source = error
        else:
            outcome = Outcome.OK
            source = rpc.get("result")
        step_type = StepType.OBSERVE
        ended_at = event_time

    # Mask secrets before any storage transform (DD-06); detection runs even
    # when content is not captured so a secret-detected event still fires (R5).
    masked_source, kinds = redact_mapping(source)
    masked_resource: dict[str, Any] | None = None
    if resource is not None:
        # The resource URI is metadata (searchable by ``search --mcp-resource``);
        # it still passes through secret detection so an embedded secret leaves a
        # masked trace rather than leaking.
        masked_resource, resource_kinds = redact_mapping({"uri": resource})
        kinds = (*kinds, *resource_kinds)
    security_event = (
        SecurityEvent(
            type=SecurityEventType.SECRET_DETECTED,
            emitted_at=event_time,
            emitter="agentwatch",
            tool=tool_name,
            evidence={"kinds": list(kinds)},
        )
        if kinds
        else None
    )
    captured, privacy_mode = _capture(masked_source, redaction)

    tool_kwargs: dict[str, Any] = {"name": tool_name, "server": server}
    if masked_resource is not None:
        tool_kwargs["arguments"] = masked_resource
        tool_kwargs["privacy_mode"] = RecordPrivacyMode.METADATA_ONLY
    if captured is not None:
        tool_kwargs["privacy_mode"] = privacy_mode
        if direction == "request":
            tool_kwargs["arguments"] = captured
        else:
            tool_kwargs["response"] = captured

    record = AgentRecord(
        session_id=session_id,
        agent=AgentIdentity(identity="unknown"),
        tool=ToolCall(**tool_kwargs),
        outcome=outcome,
        started_at=event_time,
        harness=HARNESS_ID,
        producer=PROXY_PRODUCER,
        trace_id=str(event.get("trace_id") or session_id),
        span_id=_span_id(server, event, rpc),
        project=project,
        ended_at=ended_at,
        step_type=step_type,
        security_event=security_event,
    )
    return [record]
