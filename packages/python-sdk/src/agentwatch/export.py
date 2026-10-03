"""OTLP export orchestrator (M5 5.1/5.3, R4).

Turns the local, redacted, hash-chained store into OpenTelemetry spans and
forwards them to a backend the operator owns. Export is deliberately decoupled
from recording: the store is the source of truth, the exporter only reads it, so
an endpoint outage can never cost local data (F5).

The transport is injected as a :class:`SpanSink`; :class:`OTelSpanSink` is the
OpenTelemetry implementation. The optional OTLP gRPC package is imported lazily
by :func:`otlp_sink`, keeping the core SDK dependency-light.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter
from opentelemetry.trace import NonRecordingSpan, SpanContext, Status, StatusCode, TraceFlags

from agentwatch.attrs import (
    GEN_AI_AGENT_NAME,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_OPERATION_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_TOOL_NAME,
    SPAN_KIND_TOOL,
)
from agentwatch.records import AgentRecord, Outcome, SecurityEvent
from agentwatch.store import RecordStore


class ExportError(Exception):
    """Raised by a sink when a record could not be delivered to the backend."""


@runtime_checkable
class SpanSink(Protocol):
    """A destination for exported records; raises :class:`ExportError` on failure."""

    def emit(self, record: AgentRecord, *, seq: int) -> None:
        """Deliver one record; raise :class:`ExportError` if it was not accepted."""
        ...


@dataclass(frozen=True)
class ExportReport:
    """Outcome of one export pass.

    ``attempted`` counts records considered; ``exported`` counts records
    delivered. On a sink failure ``exported < attempted`` and ``error`` is set,
    while the store is left untouched (F5).
    """

    exported: int
    attempted: int
    last_seq: int
    error: str | None = None
    blocked: bool = False
    reset: bool = False


# --- span construction ------------------------------------------------------


def _to_ns(value: datetime) -> int:
    """Convert an aware datetime to OTel's nanosecond Unix representation."""
    return int(value.timestamp() * 1_000_000_000)


def _format_id(value: str, *, nbytes: int) -> int:
    """Coerce an arbitrary id string into a non-zero integer of ``nbytes`` bytes.

    Valid hex ids of the right width are preserved (round-tripping W3C trace
    context); anything else is hashed deterministically so the same logical id
    always maps to the same OTel id across exports.
    """
    text = value.strip().lower()
    if len(text) == nbytes * 2:
        try:
            candidate = int(text, 16)
            if candidate:
                return candidate
        except ValueError:
            pass
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[: nbytes * 2], 16) or 1


def _parent_context(record: AgentRecord) -> SpanContext:
    """Build the parent (or synthetic session-root) span context for a record.

    Records in a session share ``trace_id`` so they form one trace. When the
    harness supplied no parent, a deterministic synthetic root keeps the trace
    grouping instead of scattering each record into its own trace.
    """
    logical_trace = record.trace_id or record.session_id
    trace_id = _format_id(logical_trace, nbytes=16)
    if record.parent_span_id is not None:
        span_id = _format_id(record.parent_span_id, nbytes=8)
    else:
        span_id = _format_id(f"{logical_trace}:root", nbytes=8)
    return SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )


def record_to_attributes(record: AgentRecord, seq: int) -> dict[str, Any]:
    """Map a record to OTel GenAI attributes (design: otel-mapping.md)."""
    attributes: dict[str, Any] = {
        GEN_AI_OPERATION_NAME: SPAN_KIND_TOOL,
        GEN_AI_TOOL_NAME: record.tool.name,
        GEN_AI_CONVERSATION_ID: record.session_id,
        GEN_AI_AGENT_NAME: record.agent.name or record.agent.identity,
        "agentwatch.seq": seq,
    }
    if record.agent.version is not None:
        attributes["gen_ai.agent.version"] = record.agent.version
    if record.agent.model_version is not None:
        attributes[GEN_AI_REQUEST_MODEL] = record.agent.model_version
    if record.agent.workload_type is not None:
        attributes["gen_ai.agent.workload.type"] = record.agent.workload_type
    if record.tool.server is not None:
        attributes["mcp.server"] = record.tool.server
    if record.harness is not None:
        attributes["agentwatch.harness"] = record.harness
    if record.duration_ms is not None:
        attributes["agentwatch.duration_ms"] = record.duration_ms
    if record.tokens is not None:
        attributes["gen_ai.usage.total_tokens"] = record.tokens
    if record.cost_usd is not None:
        attributes["gen_ai.agent.run.cost.total"] = record.cost_usd
    return attributes


def security_event_attributes(event: SecurityEvent) -> dict[str, Any]:
    """Map a security event to attributes for an OTel span event (DD-14)."""
    attributes: dict[str, Any] = {"event_version": event.event_version}
    for key, value in {
        "emitter": event.emitter,
        "reason": event.reason,
        "policy_id": event.policy_id,
        "tool": event.tool,
        "credential_ref": event.credential_ref,
    }.items():
        if value is not None:
            attributes[key] = value
    if event.evidence is not None:
        attributes["evidence"] = json.dumps(event.evidence, sort_keys=True)
    return attributes


_STATUS_BY_OUTCOME = {
    Outcome.ERROR: StatusCode.ERROR,
    Outcome.DENIED: StatusCode.ERROR,
}


class OTelSpanSink:
    """An :class:`SpanSink` that forwards each record as one OTel span.

    When an ``exporter`` is supplied it is attached synchronously (via
    ``SimpleSpanProcessor``) so delivery failures are observable in-process; the
    OTLP gRPC exporter is built lazily by :func:`otlp_sink`.
    """

    def __init__(self, provider: TracerProvider, *, exporter: SpanExporter | None = None) -> None:
        self._provider = provider
        self._tracer = provider.get_tracer("agentwatch.export")
        if exporter is not None:
            provider.add_span_processor(SimpleSpanProcessor(exporter))

    def emit(self, record: AgentRecord, *, seq: int) -> None:
        """Export one record as an OTel span (and its security event, if any)."""
        context = trace.set_span_in_context(NonRecordingSpan(_parent_context(record)))
        span = self._tracer.start_span(
            record.tool.name,
            context=context,
            start_time=_to_ns(record.started_at),
        )
        for key, value in record_to_attributes(record, seq).items():
            span.set_attribute(key, value)
        if record.security_event is not None:
            span.add_event(
                record.security_event.type.value,
                security_event_attributes(record.security_event),
            )
        span.set_status(Status(_STATUS_BY_OUTCOME.get(record.outcome, StatusCode.UNSET)))
        end = record.ended_at or record.started_at
        span.end(end_time=_to_ns(end))


class ExportOrchestrator:
    """Reads the store and forwards :class:`SpanSink` emissions in chain order."""

    def __init__(self, store: RecordStore, sink: SpanSink) -> None:
        self._store = store
        self._sink = sink

    def export_pending(self) -> ExportReport:
        """Export every live record currently in the store, in order."""
        exported = 0
        attempted = 0
        last_seq = -1
        for entry in self._store.entries():
            if entry.record is None:
                continue
            attempted += 1
            self._sink.emit(entry.record, seq=entry.seq)
            exported += 1
            last_seq = entry.seq
        return ExportReport(exported=exported, attempted=attempted, last_seq=last_seq)
