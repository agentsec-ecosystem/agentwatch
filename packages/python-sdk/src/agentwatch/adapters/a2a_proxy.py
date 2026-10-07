"""A2A proxy adapter: interposition frames -> agentwatch records (M29 A2A-1 #364).

The proxy emits one JSON-RPC message per frame::

    {"phase": "a2a", "harness": "a2a-proxy", "event": {
        "agent": "remote-scheduler", "session_id": "s-1",
        "direction": "request" | "response" | "card",
        "tool_name": "message/send",          # required on a response
        "rpc": { ...JSON-RPC 2.0 message... },
        "card": { ...A2A agent card... },     # on a card exchange
        "task_id": "t-1", "message_id": "m-1",
        "timestamp": "...", "cwd": "/repo"}}

A ``message/send`` / ``message/stream`` / ``tasks/*`` request yields an *intent*
record (``step_type=act``); its response yields an *outcome* record
(``step_type=observe``, ``error`` on a JSON-RPC error, sharing the request's
``span_id``). Each artifact carried by a task result is recorded as its own
``a2a/artifact`` observation. An agent-card exchange is recorded as an
``a2a/agent-card`` observation with a content digest. Anything else — a declared
gap, an unknown phase, an unresolvable method — is rejected explicitly, never
dropped (PRD 17), and the proxy relays it unchanged.

Redaction runs here, before a record leaves the adapter (DD-06): by default no
content is captured (metadata-only). A detected secret always emits a
``secret-detected`` security event, even when content is not captured (R5).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, cast
from urllib.parse import urlsplit

from agentwatch import agent_card
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

HARNESS_ID = "a2a-proxy"

# Interposed A2A traffic is proxy-produced (M15 S26).
PROXY_PRODUCER = Producer(kind=ProducerKind.PROXY, name=HARNESS_ID)

# Capability classes this adapter implements; anything else is a documented gap.
CAPABILITIES = frozenset({"a2a-messages", "a2a-tasks", "a2a-artifacts", "a2a-agent-card"})

# Honest, declared gaps — never dropped silently (R3). Resubscribe and the
# push-notification-config family are relayed unchanged, not recorded.
DOCUMENTED_GAPS = ("a2a-push-notifications", "a2a-resubscribe", "a2a-extended-card")

# The A2A methods that are recorded (mirrors ``a2a_proxy.RECORDABLE_METHODS``).
_RECORDABLE_METHODS = frozenset({"message/send", "message/stream", "tasks/get", "tasks/cancel"})
_MESSAGE_METHODS = frozenset({"message/send", "message/stream"})

_ARTIFACT_TOOL = "a2a/artifact"
_CARD_TOOL = "a2a/agent-card"

_PRIVACY_MAP = {
    PrivacyMode.METADATA_ONLY: RecordPrivacyMode.METADATA_ONLY,
    PrivacyMode.TRUNCATED: RecordPrivacyMode.TRUNCATED,
    PrivacyMode.HASHED: RecordPrivacyMode.HASHED,
    PrivacyMode.FULL: RecordPrivacyMode.FULL,
}


class A2aProxyAdapterError(ValueError):
    """Raised when an A2A proxy frame cannot be normalized."""


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
        raise A2aProxyAdapterError(f"invalid timestamp {raw!r}") from exc


def _span_id(agent: str, event: Mapping[str, Any], rpc: Mapping[str, Any]) -> str | None:
    """Correlate a call. A proxy-assigned ``call_id`` wins; else the JSON-RPC id."""
    call_id = event.get("call_id")
    if isinstance(call_id, str) and call_id:
        return f"a2a:{agent}:{call_id}"
    raw_id = rpc.get("id")
    if raw_id is None or isinstance(raw_id, bool):
        return None
    return f"a2a:{agent}:{raw_id}"


def _request_metadata(method: str, params: Mapping[str, Any]) -> dict[str, str]:
    """The correlation ids carried by a recorded A2A request."""
    metadata: dict[str, str] = {}
    if method in _MESSAGE_METHODS:
        raw_message = params.get("message")
        message = raw_message if isinstance(raw_message, Mapping) else {}
        for key, field in (
            ("task_id", "taskId"),
            ("message_id", "messageId"),
            ("context_id", "contextId"),
        ):
            value = message.get(field)
            if isinstance(value, str) and value:
                metadata[key] = value
    else:
        value = params.get("id")
        if isinstance(value, str) and value:
            metadata["task_id"] = value
    return metadata


def _response_metadata(event: Mapping[str, Any], rpc: Mapping[str, Any]) -> dict[str, str]:
    """The correlation ids carried by a recorded A2A response."""
    metadata: dict[str, str] = {}
    result = rpc.get("result")
    if isinstance(result, Mapping):
        kind = result.get("kind")
        if kind == "task":
            task_id = result.get("id")
            if isinstance(task_id, str) and task_id:
                metadata["task_id"] = task_id
            status = result.get("status")
            state = status.get("state") if isinstance(status, Mapping) else None
            if isinstance(state, str) and state:
                metadata["state"] = state
        elif kind == "message":
            message_id = result.get("messageId")
            if isinstance(message_id, str) and message_id:
                metadata["message_id"] = message_id
            role = result.get("role")
            if isinstance(role, str) and role:
                metadata["role"] = role
    for key in ("task_id", "message_id", "context_id"):
        value = event.get(key)
        if key not in metadata and isinstance(value, str) and value:
            metadata[key] = value
    return metadata


def _artifacts(result: Any) -> list[Mapping[str, Any]]:
    """The artifacts carried by an A2A task result."""
    if not isinstance(result, Mapping):
        return []
    raw = result.get("artifacts")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _card_host(card: Mapping[str, Any]) -> str | None:
    url = card.get("url")
    if isinstance(url, str) and url:
        return urlsplit(url).hostname
    return None


def _card_provenance(agent: str, card: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic signed-card provenance recorded with the exchange (A2A-2).

    The verification outcome is evidence, never an authorization; a card whose
    key we do not hold is recorded ``unverified`` with a reason.
    """
    provenance = agent_card.verify_agent_card(card).to_dict()
    if not provenance.get("agent"):
        provenance["agent"] = agent
    return provenance


def _delegation_record(
    agent: str,
    event: Mapping[str, Any],
    *,
    request_metadata: dict[str, Any],
    event_time: datetime,
    session_id: str,
    project: str | None,
    trace_id: str,
    parent_span: str | None,
) -> AgentRecord | None:
    """Build the cross-agent delegation observation, or ``None`` if not cross-org."""
    raw_card = event.get("card")
    card = raw_card if isinstance(raw_card, Mapping) else None
    provenance = _card_provenance(agent, card) if card is not None else None

    remote_org = event.get("remote_org")
    if not isinstance(remote_org, str) or not remote_org:
        remote_org = provenance.get("org") if provenance is not None else None
    remote_host = event.get("remote_host")
    if not isinstance(remote_host, str) or not remote_host:
        remote_host = _card_host(card) if card is not None else None
    if remote_org is None and card is None:
        return None

    remote_agent = agent
    if provenance is not None and isinstance(provenance.get("agent"), str):
        remote_agent = str(provenance["agent"])
    evidence: dict[str, Any] = {
        "remote_agent": remote_agent,
        "remote_org": remote_org,
        "remote_host": remote_host,
        **request_metadata,
    }
    if provenance is not None:
        evidence["card_digest"] = provenance["card_digest"]
        evidence["card_outcome"] = provenance["outcome"]
    masked_evidence, kinds = redact_mapping({k: v for k, v in evidence.items() if v is not None})
    arguments: dict[str, Any] = {
        key: value
        for key, value in (
            ("remote_agent", remote_agent),
            ("remote_org", remote_org),
            ("remote_host", remote_host),
        )
        if value is not None
    }
    masked_arguments, arg_kinds = redact_mapping(arguments)
    kinds = (*kinds, *arg_kinds)

    local_agent = event.get("local_agent")
    chain: tuple[str, ...] | None = None
    if isinstance(local_agent, str) and local_agent:
        chain = (local_agent, remote_agent)
    elif remote_agent:
        chain = (remote_agent,)
    workload_identity = None
    if card is not None and isinstance(card.get("url"), str):
        workload_identity = str(card["url"])

    span_id = f"{parent_span}:delegation" if parent_span else f"a2a:{agent}:delegation"
    return AgentRecord(
        session_id=session_id,
        agent=AgentIdentity(
            identity=remote_agent,
            name=provenance.get("agent") if provenance is not None else None,
            delegation_chain=chain,
            workload_identity=workload_identity,
        ),
        tool=ToolCall(
            name="agent-delegation",
            server=remote_agent,
            arguments=masked_arguments,
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
        outcome=Outcome.OK,
        started_at=event_time,
        harness=HARNESS_ID,
        producer=PROXY_PRODUCER,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span,
        project=project,
        host=remote_host,
        ended_at=event_time,
        step_type=StepType.OBSERVE,
        security_event=SecurityEvent(
            type=SecurityEventType.AGENT_DELEGATION,
            emitted_at=event_time,
            emitter="agentwatch",
            reason="cross-agent delegation observed",
            tool="agent-delegation",
            evidence={**masked_evidence, **({"kinds": list(kinds)} if kinds else {})},
        ),
    )


def normalize(
    message: Mapping[str, Any],
    *,
    redaction: RedactionConfig | None = None,
) -> list[AgentRecord]:
    """Normalize one A2A proxy frame into one or more records (or raise).

    Raises:
        A2aProxyAdapterError: when the frame is not a recordable A2A surface or
            names an unsupported phase (declared gaps are rejected explicitly,
            never dropped).
    """
    if not isinstance(message, Mapping):
        raise A2aProxyAdapterError("hook message must be an object")

    if message.get("phase") != "a2a":
        raise A2aProxyAdapterError(f"unsupported phase {message.get('phase')!r}; expected 'a2a'")

    event = message.get("event")
    if not isinstance(event, Mapping):
        raise A2aProxyAdapterError("hook message is missing an 'event' object")

    direction = event.get("direction")
    if direction not in ("request", "response", "card"):
        raise A2aProxyAdapterError(
            f"unsupported direction {direction!r}; expected 'request', 'response', or 'card'"
        )

    agent = event.get("agent")
    if not isinstance(agent, str) or not agent:
        raise A2aProxyAdapterError("event is missing an 'agent'")

    session_id = str(event.get("session_id") or "unknown")
    project = event.get("cwd") if isinstance(event.get("cwd"), str) else None
    event_time = _event_time(event)
    trace_id = str(event.get("trace_id") or session_id)

    if direction == "card":
        return [_card_record(agent, event, event_time, session_id, project, trace_id)]

    rpc = event.get("rpc")
    if not isinstance(rpc, Mapping):
        raise A2aProxyAdapterError("event is missing an 'rpc' object")

    if direction == "request":
        method = rpc.get("method")
        params = rpc.get("params")
        if not isinstance(params, Mapping):
            raise A2aProxyAdapterError(f"{method!r} is missing a 'params' object")
        if method not in _RECORDABLE_METHODS:
            raise A2aProxyAdapterError(
                f"unsupported method {method!r}; expected 'message/send', 'message/stream', "
                f"'tasks/get', or 'tasks/cancel'"
            )
        tool_name = str(method)
        metadata = _request_metadata(tool_name, params)
        if tool_name in _MESSAGE_METHODS:
            raw_message = params.get("message")
            if not isinstance(raw_message, Mapping):
                raise A2aProxyAdapterError(f"{tool_name} is missing a 'message' object")
            source: Any = raw_message
        else:
            source = None
        step_type: StepType | None = StepType.ACT
        outcome = Outcome.OK
        ended_at: datetime | None = None
    else:
        name = event.get("tool_name")
        if not isinstance(name, str) or not name:
            raise A2aProxyAdapterError("response is missing a 'tool_name'")
        tool_name = name
        error = rpc.get("error")
        outcome = Outcome.ERROR if error is not None else Outcome.OK
        source = error if error is not None else rpc.get("result")
        metadata = _response_metadata(event, rpc)
        step_type = StepType.OBSERVE
        ended_at = event_time

    masked_source, kinds = redact_mapping(source)
    masked_metadata: dict[str, Any] | None = None
    if metadata:
        masked_metadata, metadata_kinds = redact_mapping(metadata)
        kinds = (*kinds, *metadata_kinds)
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

    tool_kwargs: dict[str, Any] = {"name": tool_name, "server": agent}
    if masked_metadata is not None:
        tool_kwargs["arguments"] = masked_metadata
        tool_kwargs["privacy_mode"] = RecordPrivacyMode.METADATA_ONLY
    if captured is not None:
        tool_kwargs["privacy_mode"] = privacy_mode
        if direction == "request":
            tool_kwargs["arguments"] = captured
        else:
            tool_kwargs["response"] = captured

    span = _span_id(agent, event, rpc)
    parent_span_id = event.get("parent_span_id")
    record = AgentRecord(
        session_id=session_id,
        agent=AgentIdentity(identity=agent),
        tool=ToolCall(**tool_kwargs),
        outcome=outcome,
        started_at=event_time,
        harness=HARNESS_ID,
        producer=PROXY_PRODUCER,
        trace_id=trace_id,
        span_id=span,
        parent_span_id=parent_span_id if isinstance(parent_span_id, str) else None,
        project=project,
        ended_at=ended_at,
        step_type=step_type,
        security_event=security_event,
    )
    records = [record]
    if direction == "request" and tool_name in _MESSAGE_METHODS:
        delegation = _delegation_record(
            agent,
            event,
            request_metadata=masked_metadata or {},
            event_time=event_time,
            session_id=session_id,
            project=project,
            trace_id=trace_id,
            parent_span=span,
        )
        if delegation is not None:
            # The outbound call itself is on-behalf-of the local agent; carry the
            # same chain on the intent record so tree/trace render the cross-org hop.
            chain = delegation.agent.delegation_chain
            if chain:
                record = replace(record, agent=replace(record.agent, delegation_chain=chain))
                records = [record]
            records.append(delegation)
    if direction == "response":
        records.extend(
            _artifact_records(
                agent, event, rpc, event_time, session_id, project, trace_id, span
            )
        )
    return records


def _artifact_records(
    agent: str,
    event: Mapping[str, Any],
    rpc: Mapping[str, Any],
    event_time: datetime,
    session_id: str,
    project: str | None,
    trace_id: str,
    span: str | None,
) -> list[AgentRecord]:
    """Record each artifact carried by a task result as its own observation."""
    records: list[AgentRecord] = []
    for index, artifact in enumerate(_artifacts(rpc.get("result"))):
        artifact_id = artifact.get("artifactId")
        name = artifact.get("name")
        metadata: dict[str, Any] = {}
        if isinstance(artifact_id, str) and artifact_id:
            metadata["artifact_id"] = artifact_id
        if isinstance(name, str) and name:
            metadata["name"] = name
        masked, kinds = redact_mapping(metadata)
        security_event = (
            SecurityEvent(
                type=SecurityEventType.SECRET_DETECTED,
                emitted_at=event_time,
                emitter="agentwatch",
                tool=_ARTIFACT_TOOL,
                evidence={"kinds": list(kinds)},
            )
            if kinds
            else None
        )
        records.append(
            AgentRecord(
                session_id=session_id,
                agent=AgentIdentity(identity=agent),
                tool=ToolCall(
                    name=_ARTIFACT_TOOL,
                    server=agent,
                    arguments=masked,
                    privacy_mode=RecordPrivacyMode.METADATA_ONLY,
                ),
                outcome=Outcome.OK,
                started_at=event_time,
                harness=HARNESS_ID,
                producer=PROXY_PRODUCER,
                trace_id=trace_id,
                span_id=f"{span}-artifact-{index}" if span else None,
                project=project,
                ended_at=event_time,
                step_type=StepType.OBSERVE,
                security_event=security_event,
            )
        )
    return records


def _card_record(
    agent: str,
    event: Mapping[str, Any],
    event_time: datetime,
    session_id: str,
    project: str | None,
    trace_id: str,
) -> AgentRecord:
    """Record an agent-card exchange with its content digest (metadata-only)."""
    card = event.get("card")
    if not isinstance(card, Mapping):
        raise A2aProxyAdapterError("card exchange is missing a 'card' object")
    provenance = _card_provenance(agent, card)
    masked, kinds = redact_mapping(provenance)
    security_event = (
        SecurityEvent(
            type=SecurityEventType.SECRET_DETECTED,
            emitted_at=event_time,
            emitter="agentwatch",
            tool=_CARD_TOOL,
            evidence={"kinds": list(kinds)},
        )
        if kinds
        else None
    )
    name = card.get("name")
    source = event.get("source")
    card_meta: dict[str, Any] = {"card": provenance}
    if isinstance(source, str) and source:
        card_meta["source"] = source
    environment: dict[str, Any] = {"a2a": card_meta}
    digest = str(provenance["card_digest"])
    return AgentRecord(
        session_id=session_id,
        agent=AgentIdentity(
            identity=agent, name=name if isinstance(name, str) and name else None
        ),
        tool=ToolCall(
            name=_CARD_TOOL,
            server=agent,
            arguments=masked,
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
        outcome=Outcome.OK,
        started_at=event_time,
        harness=HARNESS_ID,
        producer=PROXY_PRODUCER,
        trace_id=trace_id,
        span_id=f"a2a:{agent}:card:{digest[:12]}",
        project=project,
        host=_card_host(card),
        ended_at=event_time,
        step_type=StepType.OBSERVE,
        environment=environment,
        security_event=security_event,
    )


__all__ = [
    "CAPABILITIES",
    "DOCUMENTED_GAPS",
    "HARNESS_ID",
    "PROXY_PRODUCER",
    "A2aProxyAdapterError",
    "normalize",
]