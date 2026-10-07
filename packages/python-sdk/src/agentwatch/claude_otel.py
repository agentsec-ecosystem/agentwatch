"""Claude Code native OTel ingest + ``tool_use_id`` join (M29 CCO-1, PRD 51).

Claude Code exports its own OpenTelemetry — structured events (``tool_decision``
with ``decision_source``, ``permission_mode_changed``, ``api_request``,
``tool_result``, ``user_prompt``, ``mcp_server_connection``), metrics and beta
traces — correlated by ``tool_use_id``/``prompt.id``. This module maps that stream
into the record model and **joins** it to hook records by ``tool_use_id``; a
disagreement between the two sources is a classified observation, never silently
reconciled.

The hook path stays the zero-config default. Native telemetry is exact (vendor
cost, authoritative decision source); foreign/unmappable input is a problem the
caller quarantines (B4). Redaction runs on ingest regardless of capture options.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

from agentwatch.authorization import authorization_from_decision_source, permission_mode_from
from agentwatch.ingest import (
    IngestProblem,
    _any_value,
    _attributes,
    _flatten_spans,
    _nanos,
)
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Authorization,
    AuthorizationDeny,
    AuthorizationEvidence,
    AuthorizationSource,
    Outcome,
    PermissionMode,
    Producer,
    ProducerKind,
    RecordPrivacyMode,
    SecurityEvent,
    SecurityEventType,
    StepType,
    ToolCall,
    effective_authorization,
    effective_producer,
    validate_record,
)
from agentwatch.redact import PrivacyMode, RedactionConfig
from agentwatch.secrets import redact_mapping

HARNESS_ID = "claude-code"

# Native telemetry producers (CCO-1 OTel, CCO-2 Agent SDK/headless).
OTEL_PRODUCER = Producer(kind=ProducerKind.INGEST, name="claude-code-otel")
SDK_PRODUCER = Producer(kind=ProducerKind.SDK, name="sdk-native")
OTEL_PRODUCER_NAMES = frozenset({OTEL_PRODUCER.name or "", SDK_PRODUCER.name or ""})

_PRIVACY_MAP = {
    PrivacyMode.METADATA_ONLY: RecordPrivacyMode.METADATA_ONLY,
    PrivacyMode.TRUNCATED: RecordPrivacyMode.TRUNCATED,
    PrivacyMode.HASHED: RecordPrivacyMode.HASHED,
    PrivacyMode.FULL: RecordPrivacyMode.FULL,
}

# Native event names we map (the ``claude_code.`` prefix is optional).
_EVENT_PREFIX = "claude_code."
_DENY_DECISIONS = frozenset({"deny", "denied", "reject", "block", "blocked"})
_ERROR_STATUS = frozenset({"error", "failed", "failure"})

# Events that are observations, not agent tool calls (coverage must not count them).
NON_TOOL_EVENTS = frozenset({"permission-mode-changed", "mcp-server-connection"})


class ClaudeOtelError(ValueError):
    """Raised when a native telemetry element cannot be mapped."""


# ---------------------------------------------------------------------------
# OTLP decoding
# ---------------------------------------------------------------------------


def _first_str(source: Mapping[str, Any], keys: Iterable[str]) -> str | None:
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _event_name(log: Mapping[str, Any]) -> str | None:
    body = log.get("body")
    name: object = None
    if isinstance(body, str):
        name = body
    elif isinstance(body, Mapping):
        name = _any_value(body)
    if not isinstance(name, str) or not name:
        attrs = _attributes(log.get("attributes"))
        fallback = attrs.get("event.name") or attrs.get("name")
        name = fallback if isinstance(fallback, str) else None
    if not isinstance(name, str) or not name:
        return None
    return name[len(_EVENT_PREFIX):] if name.startswith(_EVENT_PREFIX) else name


def _iter_log_records(payload: Any) -> Iterable[tuple[dict[str, Any], Mapping[str, Any]]]:
    if not isinstance(payload, Mapping):
        return
    resource_logs = payload.get("resourceLogs")
    if not isinstance(resource_logs, list):
        return
    for resource_log in resource_logs:
        if not isinstance(resource_log, Mapping):
            continue
        resource = resource_log.get("resource")
        resource_attrs = (
            _attributes(resource.get("attributes")) if isinstance(resource, Mapping) else {}
        )
        scope_logs = resource_log.get("scopeLogs") or resource_log.get("instrumentationLibraryLogs")
        if not isinstance(scope_logs, list):
            continue
        for scope_log in scope_logs:
            if not isinstance(scope_log, Mapping):
                continue
            records = scope_log.get("logRecords") or scope_log.get("logs")
            if not isinstance(records, list):
                continue
            for log in records:
                if isinstance(log, Mapping):
                    yield resource_attrs, log


def _iter_metric_points(payload: Any) -> Iterable[tuple[str, dict[str, Any], Mapping[str, Any]]]:
    if not isinstance(payload, Mapping):
        return
    resource_metrics = payload.get("resourceMetrics")
    if not isinstance(resource_metrics, list):
        return
    for resource_metric in resource_metrics:
        if not isinstance(resource_metric, Mapping):
            continue
        resource = resource_metric.get("resource")
        resource_attrs = (
            _attributes(resource.get("attributes")) if isinstance(resource, Mapping) else {}
        )
        scope_metrics = resource_metric.get("scopeMetrics")
        if not isinstance(scope_metrics, list):
            continue
        for scope_metric in scope_metrics:
            if not isinstance(scope_metric, Mapping):
                continue
            metrics = scope_metric.get("metrics")
            if not isinstance(metrics, list):
                continue
            for metric in metrics:
                if not isinstance(metric, Mapping):
                    continue
                name = metric.get("name")
                if not isinstance(name, str):
                    continue
                for kind in ("sum", "gauge", "histogram"):
                    data = metric.get(kind)
                    if not isinstance(data, Mapping):
                        continue
                    points = data.get("dataPoints") or data.get("data_points")
                    if not isinstance(points, list):
                        continue
                    for point in points:
                        if not isinstance(point, Mapping):
                            continue
                        attrs = _attributes(point.get("attributes"))
                        merged = {**resource_attrs, **attrs}
                        merged.setdefault("_value", point.get("asDouble", point.get("asInt")))
                        normalized = (
                            name[len(_EVENT_PREFIX):] if name.startswith(_EVENT_PREFIX) else name
                        )
                        yield normalized, merged, point


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------


def _identity(attrs: Mapping[str, Any], resource: Mapping[str, Any]) -> AgentIdentity:
    identity = (
        _first_str(resource, ("agentwatch.identity",))
        or _first_str(attrs, ("agentwatch.identity",))
        or _first_str(attrs, ("agent",))
        or _first_str(resource, ("service.name",))
        or "unknown"
    )
    return AgentIdentity(identity=identity, name=_first_str(resource, ("service.name",)))


def _timestamp(payload: Mapping[str, Any]) -> datetime:
    for key in ("timeUnixNano", "observedTimeUnixNano", "startTimeUnixNano"):
        parsed = _nanos(payload.get(key))
        if parsed is not None:
            return parsed
    return datetime.now(timezone.utc)


def _tokens(attrs: Mapping[str, Any]) -> int | None:
    total = attrs.get("total_tokens", attrs.get("gen_ai.usage.total_tokens"))
    if isinstance(total, int) and not isinstance(total, bool):
        return total
    prompt = attrs.get("input_tokens", attrs.get("gen_ai.usage.input_tokens"))
    completion = attrs.get("output_tokens", attrs.get("gen_ai.usage.output_tokens"))
    if prompt is None and completion is None:
        value = attrs.get("_value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
        return None
    try:
        return int(prompt or 0) + int(completion or 0)
    except (TypeError, ValueError):
        return None


def _cost(attrs: Mapping[str, Any]) -> float | None:
    for key in ("cost_usd", "cost", "gen_ai.usage.cost", "gen_ai.usage.total_cost"):
        value = attrs.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _redact(value: Any, cfg: RedactionConfig) -> Any:
    if isinstance(value, str):
        return cfg.apply(value, allowed=True)
    if isinstance(value, Mapping):
        return {key: _redact(item, cfg) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, cfg) for item in value]
    return value


def _captured_text(value: Any, cfg: RedactionConfig | None) -> tuple[str | None, RecordPrivacyMode]:
    if not isinstance(value, str) or not value:
        return None, RecordPrivacyMode.METADATA_ONLY
    if cfg is None or cfg.mode is PrivacyMode.METADATA_ONLY or not cfg.capture_prompts:
        return None, RecordPrivacyMode.METADATA_ONLY
    masked, _ = redact_mapping(value)
    applied = cfg.apply(masked if isinstance(masked, str) else value, allowed=True)
    if not isinstance(applied, str):
        return None, RecordPrivacyMode.METADATA_ONLY
    return applied, _PRIVACY_MAP[cfg.mode]


def _secret_event(tool: str, raw: Any, at: datetime) -> SecurityEvent | None:
    _, kinds = redact_mapping(raw)
    if not kinds:
        return None
    return SecurityEvent(
        type=SecurityEventType.SECRET_DETECTED,
        emitted_at=at,
        emitter="agentwatch",
        tool=tool,
        evidence={"kinds": list(kinds)},
    )


def _base_record(
    attrs: Mapping[str, Any],
    resource: Mapping[str, Any],
    *,
    tool: str,
    producer: Producer,
    at: datetime,
    span_id: str | None,
    outcome: Outcome = Outcome.OK,
    step_type: StepType | None = StepType.OBSERVE,
    arguments: dict[str, Any] | None = None,
    privacy_mode: RecordPrivacyMode | None = None,
    tokens: int | None = None,
    cost_usd: float | None = None,
    authorization: Authorization | None = None,
    permission_mode: PermissionMode | None = None,
    security_event: SecurityEvent | None = None,
    duration_ms: float | None = None,
) -> AgentRecord:
    session_id = (
        _first_str(attrs, ("session.id", "session_id", "conversation.id"))
        or _first_str(resource, ("session.id",))
        or "unknown"
    )
    record = AgentRecord(
        session_id=session_id,
        agent=_identity(attrs, resource),
        tool=ToolCall(name=tool, arguments=arguments, privacy_mode=privacy_mode),
        outcome=outcome,
        started_at=at,
        harness=HARNESS_ID,
        producer=producer,
        trace_id=_first_str(attrs, ("trace_id", "traceId")) or session_id,
        span_id=span_id,
        project=_first_str(attrs, ("cwd",)),
        step_type=step_type,
        tokens=tokens,
        cost_usd=cost_usd,
        authorization=authorization,
        permission_mode=permission_mode,
        security_event=security_event,
        duration_ms=duration_ms,
    )
    validate_record(record.to_dict())
    return record


def _tool_decision(
    attrs: Mapping[str, Any], resource: Mapping[str, Any], *, at: datetime, producer: Producer
) -> AgentRecord:
    tool_use_id = _first_str(attrs, ("tool_use_id", "toolUseId"))
    decision_source = _first_str(attrs, ("decision_source",))
    authorization: Authorization | None = None
    if decision_source is not None:
        authorization = authorization_from_decision_source(decision_source)
    decision = _first_str(attrs, ("decision",))
    denied = (
        (authorization is not None and authorization.source is AuthorizationSource.DENIED)
        or decision_source == "reject"
        or (decision is not None and decision.lower() in _DENY_DECISIONS)
    )
    if authorization is None and denied:
        authorization = Authorization(
            source=AuthorizationSource.DENIED,
            deny=AuthorizationDeny.UNKNOWN,
            evidence=AuthorizationEvidence.HARNESS_NATIVE,
        )
    return _base_record(
        attrs,
        resource,
        tool=_first_str(attrs, ("tool_name",)) or "tool-decision",
        producer=producer,
        at=at,
        span_id=tool_use_id,
        outcome=Outcome.DENIED if denied else Outcome.OK,
        authorization=authorization,
    )


def _tool_result(
    attrs: Mapping[str, Any], resource: Mapping[str, Any], *, at: datetime, producer: Producer
) -> AgentRecord:
    success = attrs.get("success")
    status = attrs.get("status")
    failed = success is False or (
        isinstance(status, str) and status.lower() in _ERROR_STATUS
    )
    raw_duration = attrs.get("duration_ms", attrs.get("duration"))
    duration_ms = (
        float(raw_duration)
        if isinstance(raw_duration, (int, float)) and not isinstance(raw_duration, bool)
        else None
    )
    return _base_record(
        attrs,
        resource,
        tool=_first_str(attrs, ("tool_name",)) or "tool-result",
        producer=producer,
        at=at,
        span_id=_first_str(attrs, ("tool_use_id", "toolUseId")),
        outcome=Outcome.ERROR if failed else Outcome.OK,
        tokens=_tokens(attrs),
        cost_usd=_cost(attrs),
        duration_ms=duration_ms,
    )


def _api_request(
    attrs: Mapping[str, Any], resource: Mapping[str, Any], *, at: datetime, producer: Producer
) -> AgentRecord:
    record = _base_record(
        attrs,
        resource,
        tool="session-usage",
        producer=producer,
        at=at,
        span_id=None,
        step_type=StepType.OBSERVE,
        tokens=_tokens(attrs),
        cost_usd=_cost(attrs),
    )
    model = _first_str(attrs, ("model", "gen_ai.request.model"))
    if model is not None:
        record = replace(record, agent=replace(record.agent, model_version=model))
    return record


def _user_prompt(
    attrs: Mapping[str, Any],
    resource: Mapping[str, Any],
    *,
    at: datetime,
    producer: Producer,
    redaction: RedactionConfig | None,
) -> AgentRecord:
    raw_prompt = attrs.get("prompt")
    captured, privacy_mode = _captured_text(raw_prompt, redaction)
    arguments = {"prompt": captured} if captured is not None else None
    security_event = _secret_event("user-prompt", raw_prompt, at)
    return _base_record(
        attrs,
        resource,
        tool="user-prompt",
        producer=producer,
        at=at,
        span_id=_first_str(attrs, ("prompt.id", "prompt_id")),
        step_type=StepType.REASON,
        arguments=arguments,
        privacy_mode=privacy_mode,
        security_event=security_event,
    )


def _permission_mode_changed(
    attrs: Mapping[str, Any], resource: Mapping[str, Any], *, at: datetime, producer: Producer
) -> AgentRecord:
    from_mode = _first_str(attrs, ("from_mode", "old_mode")) or PermissionMode.UNKNOWN.value
    to_mode = _first_str(attrs, ("to_mode", "new_mode", "mode")) or PermissionMode.UNKNOWN.value
    mode = permission_mode_from(to_mode)
    return _base_record(
        attrs,
        resource,
        tool="permission-mode-changed",
        producer=producer,
        at=at,
        span_id=None,
        step_type=None,
        arguments={"from": from_mode, "to": to_mode},
        privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        permission_mode=mode if mode is not PermissionMode.UNKNOWN else None,
    )


def _mcp_server_connection(
    attrs: Mapping[str, Any], resource: Mapping[str, Any], *, at: datetime, producer: Producer
) -> AgentRecord:
    server = _first_str(attrs, ("server_name", "server", "mcp.server.name")) or "unknown"
    arguments: dict[str, Any] = {"server": server}
    transport = _first_str(attrs, ("transport",))
    if transport is not None:
        arguments["transport"] = transport
    return _base_record(
        attrs,
        resource,
        tool="mcp-server-connection",
        producer=producer,
        at=at,
        span_id=None,
        step_type=StepType.OBSERVE,
        arguments=arguments,
        privacy_mode=RecordPrivacyMode.METADATA_ONLY,
    )


_LOG_HANDLERS: dict[str, Any] = {
    "tool_decision": _tool_decision,
    "tool_result": _tool_result,
    "api_request": _api_request,
    "user_prompt": _user_prompt,
    "permission_mode_changed": _permission_mode_changed,
    "mcp_server_connection": _mcp_server_connection,
}


def _metric_record(
    name: str,
    attrs: Mapping[str, Any],
    resource: Mapping[str, Any],
    *,
    at: datetime,
    producer: Producer,
) -> AgentRecord | None:
    if name in ("token.usage", "tokens.usage"):
        return _base_record(
            attrs, resource, tool="session-usage", producer=producer, at=at, span_id=None,
            step_type=StepType.OBSERVE, tokens=_tokens(attrs),
        )
    if name in ("cost.usage", "cost"):
        return _base_record(
            attrs, resource, tool="session-usage", producer=producer, at=at, span_id=None,
            step_type=StepType.OBSERVE, cost_usd=_cost(attrs),
        )
    return None


def transcode_claude_otel(
    payload: Any,
    *,
    source: str = "claude-code-otel",
    redaction: RedactionConfig | None = None,
    producer: Producer = OTEL_PRODUCER,
) -> tuple[list[AgentRecord], list[IngestProblem]]:
    """Transcode a Claude Code OTLP payload into records + problems.

    Accepts ``resourceLogs`` (structured events), ``resourceMetrics`` (token/cost
    metrics) and traces. An unmappable structured event is a problem the caller
    quarantines (B4); an unmapped metric name is a documented skip.
    """
    records: list[AgentRecord] = []
    problems: list[IngestProblem] = []

    for index, (resource, log) in enumerate(_iter_log_records(payload)):
        here = f"{source}#log{index}"
        name = _event_name(log)
        attrs = _attributes(log.get("attributes"))
        handler = _LOG_HANDLERS.get(name or "")
        if handler is None:
            problems.append(IngestProblem(here, f"unmappable native event: {name!r}"))
            continue
        try:
            if handler is _user_prompt:
                records.append(handler(attrs, resource, at=_timestamp(log), producer=producer,
                                       redaction=redaction))
            else:
                records.append(handler(attrs, resource, at=_timestamp(log), producer=producer))
        except (ValueError, KeyError, TypeError) as exc:
            problems.append(IngestProblem(here, f"unmappable native event: {exc}"))

    for _index, (name, attrs, point) in enumerate(_iter_metric_points(payload)):
        record = _metric_record(name, attrs, {}, at=_timestamp(point), producer=producer)
        if record is not None:
            records.append(record)

    for index, span in enumerate(_flatten_spans(payload)):
        here = f"{source}#span{index}"
        attrs = _attributes(span.get("attributes"))
        name = _event_name({**span, "attributes": span.get("attributes")})
        handler = _LOG_HANDLERS.get(name or "")
        if handler is None:
            problems.append(IngestProblem(here, f"unmappable native span: {name!r}"))
            continue
        try:
            records.append(handler(attrs, {}, at=_timestamp(span), producer=producer))
        except (ValueError, KeyError, TypeError) as exc:
            problems.append(IngestProblem(here, f"unmappable native span: {exc}"))

    return records, problems


# ---------------------------------------------------------------------------
# Join (hook <-> native telemetry by tool_use_id)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Discrepancy:
    """One classified disagreement between a hook and a native-telemetry record."""

    tool_use_id: str
    field: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"tool_use_id": self.tool_use_id, "field": self.field, "detail": self.detail}


@dataclass(frozen=True)
class JoinReport:
    """The result of joining hook records to native telemetry by ``tool_use_id``."""

    joined: tuple[str, ...] = ()
    hook_only: tuple[str, ...] = ()
    otel_only: tuple[str, ...] = ()
    discrepancies: tuple[Discrepancy, ...] = ()

    def summary(self) -> str:
        return (
            f"{len(self.joined)} joined, {len(self.hook_only)} hook-only, "
            f"{len(self.otel_only)} otel-only, {len(self.discrepancies)} discrepancies "
            "(classified)"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "joined": len(self.joined),
            "hook_only": len(self.hook_only),
            "otel_only": len(self.otel_only),
            "discrepancies": [d.to_dict() for d in self.discrepancies],
            "summary": self.summary(),
        }


def is_otel_record(record: AgentRecord) -> bool:
    """Whether a record came from Claude Code's native telemetry stream."""
    return effective_producer(record).name in OTEL_PRODUCER_NAMES


def _representative(records: list[AgentRecord]) -> AgentRecord:
    """One hook record per span: prefer a completed (post) record."""
    for record in records:
        if record.ended_at is not None or record.outcome is Outcome.ERROR:
            return record
    return records[0]


def _span_key(record: AgentRecord, prefix: str, index: int) -> str:
    return record.span_id or f"anon-{prefix}:{record.session_id}:{index}"


def _merge_otel(records: list[AgentRecord]) -> dict[str, Any]:
    """Collapse the native events for one ``tool_use_id`` into one view."""
    merged: dict[str, Any] = {"outcome": None, "cost_usd": None, "authorization": None}
    for record in records:
        if (
            record.outcome is Outcome.DENIED
            or record.outcome is Outcome.ERROR
            or merged["outcome"] is None
        ):
            merged["outcome"] = record.outcome
        if record.cost_usd is not None:
            merged["cost_usd"] = record.cost_usd
        auth = effective_authorization(record)
        if auth.source is not AuthorizationSource.UNKNOWN:
            merged["authorization"] = auth
    return merged


def join_records(
    records: Iterable[AgentRecord], *, harness: str = HARNESS_ID
) -> JoinReport:
    """Join hook records to native telemetry records by ``tool_use_id``.

    A record may be hook-only, otel-only, or joined. When both sources describe a
    call and disagree on outcome/cost/authorization, the disagreement is recorded
    as a classified :class:`Discrepancy` — never silently reconciled.
    """
    hook_buckets: dict[str, list[AgentRecord]] = {}
    otel_buckets: dict[str, list[AgentRecord]] = {}
    hook_count = 0
    otel_count = 0
    for record in records:
        if is_otel_record(record):
            key = _span_key(record, "otel", otel_count)
            otel_count += 1
            otel_buckets.setdefault(key, []).append(record)
        elif effective_producer(record).kind is ProducerKind.HOOK and record.harness == harness:
            key = _span_key(record, "hook", hook_count)
            hook_count += 1
            hook_buckets.setdefault(key, []).append(record)

    joined: list[str] = []
    hook_only: list[str] = []
    otel_only: list[str] = []
    discrepancies: list[Discrepancy] = []
    for key in hook_buckets:
        if key not in otel_buckets:
            hook_only.append(key)
    for key in otel_buckets:
        if key not in hook_buckets:
            otel_only.append(key)
    for key in sorted(set(hook_buckets) & set(otel_buckets)):
        joined.append(key)
        hook = _representative(hook_buckets[key])
        otel = _merge_otel(otel_buckets[key])
        if otel["outcome"] is not None and otel["outcome"] is not hook.outcome:
            discrepancies.append(
                Discrepancy(
                    key,
                    "outcome",
                    f"hook={hook.outcome.value} otel={otel['outcome'].value}",
                )
            )
        if (
            otel["cost_usd"] is not None
            and hook.cost_usd is not None
            and abs(otel["cost_usd"] - hook.cost_usd) > 1e-9
        ):
            discrepancies.append(
                Discrepancy(
                    key, "cost", f"hook={hook.cost_usd} otel={otel['cost_usd']}"
                )
            )
        hook_auth = effective_authorization(hook)
        otel_auth = otel["authorization"]
        if (
            otel_auth is not None
            and hook_auth.source is not AuthorizationSource.UNKNOWN
            and hook_auth.source is not otel_auth.source
        ):
            discrepancies.append(
                Discrepancy(
                    key,
                    "authorization",
                    f"hook={hook_auth.source.value} otel={otel_auth.source.value}",
                )
            )
    return JoinReport(
        joined=tuple(sorted(joined)),
        hook_only=tuple(sorted(hook_only)),
        otel_only=tuple(sorted(otel_only)),
        discrepancies=tuple(discrepancies),
    )


def transcode_agent_sdk(
    payload: Any,
    *,
    source: str = "sdk-native",
    redaction: RedactionConfig | None = None,
) -> tuple[list[AgentRecord], list[IngestProblem]]:
    """Transcode a Claude Agent SDK / headless OTel payload (CCO-2).

    An Agent-SDK program runs the same CLI, so it emits the same telemetry and
    lands through the same mapping — only the producer is ``producer.kind=sdk`` /
    ``name=sdk-native`` and identity comes from the resource attributes.
    """
    return transcode_claude_otel(
        payload, source=source, redaction=redaction, producer=SDK_PRODUCER
    )


def otel_join_summary(records: Iterable[AgentRecord], *, harness: str = HARNESS_ID) -> str | None:
    """The ``coverage`` join line, or ``None`` when no native telemetry is present."""
    materialized = list(records)
    if not any(is_otel_record(record) for record in materialized):
        return None
    return join_records(materialized, harness=harness).summary()


__all__ = [
    "ClaudeOtelError",
    "Discrepancy",
    "HARNESS_ID",
    "JoinReport",
    "NON_TOOL_EVENTS",
    "OTEL_PRODUCER",
    "OTEL_PRODUCER_NAMES",
    "SDK_PRODUCER",
    "is_otel_record",
    "join_records",
    "otel_join_summary",
    "transcode_agent_sdk",
    "transcode_claude_otel",
]
