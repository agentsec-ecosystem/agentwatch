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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import NonRecordingSpan, SpanContext, Status, StatusCode, TraceFlags

from agentwatch.attrs import (
    AGENTWATCH_CREDENTIAL_CLASS,
    CONTENT_ATTRIBUTE_KEYS,
    GEN_AI_AGENT_NAME,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_OPERATION_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_TOOL_NAME,
    SPAN_KIND_TOOL,
)
from agentwatch.records import AgentRecord, Outcome, SecurityEvent
from agentwatch.selftest import export_allowed
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


# --- export cursor (F3, #184) -----------------------------------------------


@dataclass(frozen=True)
class ExportWatermark:
    """The export position: the last store ``seq`` successfully delivered."""

    last_seq: int = -1
    updated_at: datetime | None = None


class ExportState:
    """Persisted export watermark beside the store, so export resumes (F3)."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    @classmethod
    def from_store(cls, store: RecordStore) -> ExportState:
        return cls(Path(store.path).parent / "export.state.json")

    def load(self) -> ExportWatermark:
        if not self.path.exists():
            return ExportWatermark()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return ExportWatermark()
        if not isinstance(data, dict) or not isinstance(data.get("last_seq"), int):
            return ExportWatermark()
        updated = data.get("updated_at")
        stamp: datetime | None = None
        if isinstance(updated, str):
            try:
                stamp = datetime.fromisoformat(updated)
            except ValueError:
                stamp = None
        return ExportWatermark(last_seq=int(data["last_seq"]), updated_at=stamp)

    def save(self, watermark: ExportWatermark) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "last_seq": watermark.last_seq,
                    "updated_at": (
                        watermark.updated_at.isoformat()
                        if watermark.updated_at is not None
                        else None
                    ),
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def reset(self) -> None:
        self.save(ExportWatermark())


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
    if record.agent.credential_class is not None:
        attributes[AGENTWATCH_CREDENTIAL_CLASS] = record.agent.credential_class.value
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


def exported_content_keys(attributes: Mapping[str, Any]) -> tuple[str, ...]:
    """Content-bearing attribute keys present in an OTel mapping (OTEL-2 guard).

    Used to prove that no content escapes the active privacy mode on export: under
    ``metadata-only`` this must always be empty.
    """
    return tuple(sorted(key for key in attributes if key in CONTENT_ATTRIBUTE_KEYS))


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


class _TrackingExporter(SpanExporter):
    """Wrap an exporter synchronously and remember the last delivery result (F5)."""

    def __init__(self, inner: SpanExporter) -> None:
        self._inner = inner
        self.last_result = SpanExportResult.SUCCESS

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.last_result = self._inner.export(spans)
        return self.last_result

    def shutdown(self) -> None:
        self._inner.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._inner.force_flush(timeout_millis)


class OTelSpanSink:
    """An :class:`SpanSink` that forwards each record as one OTel span.

    When an ``exporter`` is supplied it is attached synchronously (via
    ``SimpleSpanProcessor``) so delivery failures are observable in-process and
    surfaced as :class:`ExportError` (F5); the OTLP gRPC exporter is built lazily
    by :func:`otlp_sink`.
    """

    def __init__(self, provider: TracerProvider, *, exporter: SpanExporter | None = None) -> None:
        self._provider = provider
        self._tracer = provider.get_tracer("agentwatch.export")
        self._tracker: _TrackingExporter | None = None
        if exporter is not None:
            self._tracker = _TrackingExporter(exporter)
            provider.add_span_processor(SimpleSpanProcessor(self._tracker))

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
        if self._tracker is not None and self._tracker.last_result is SpanExportResult.FAILURE:
            raise ExportError(f"backend rejected record at seq {seq}")


class ExportOrchestrator:
    """Reads the store and forwards :class:`SpanSink` emissions in chain order.

    Export is gated on the redaction self-test (DD-09): if the self-test fails,
    nothing is exported (F6) and the store is untouched. Recording continues
    locally regardless.
    """

    def __init__(
        self,
        store: RecordStore,
        sink: SpanSink,
        *,
        state: ExportState | None = None,
        self_test: Callable[[], bool] | None = None,
    ) -> None:
        self._store = store
        self._sink = sink
        self._state = state if state is not None else ExportState.from_store(store)
        self._explicit_state = state is not None
        self._self_test: Callable[[], bool] = self_test if self_test is not None else export_allowed

    def _persist(self, last_seq: int) -> None:
        self._state.save(ExportWatermark(last_seq=last_seq, updated_at=datetime.now(timezone.utc)))

    def export_pending(self) -> ExportReport:
        """Deliver store records after the cursor, advancing it as it goes (F3, F5).

        Export is gated on the redaction self-test (DD-09): on failure nothing is
        sent and the cursor is untouched (F6). A sink failure stops the pass, the
        cursor stays at the last delivered record, and the store is never mutated
        (F5). A cursor beyond the store (e.g. after a repair, E2) is reset with a
        notice instead of silently re-exporting or skipping.
        """
        watermark = self._state.load()
        if not self._self_test():
            return ExportReport(exported=0, attempted=0, last_seq=watermark.last_seq, blocked=True)
        entries = self._store.entries()
        last_entry_seq = entries[-1].seq if entries else -1
        reset = False
        if watermark.last_seq > last_entry_seq:
            self._state.reset()
            watermark = self._state.load()
            reset = True

        exported = 0
        attempted = 0
        cursor = watermark.last_seq
        for entry in entries:
            if entry.seq <= cursor:
                continue
            if entry.record is None:  # tombstone: advance past it, do not export
                if self._explicit_state:
                    cursor = entry.seq
                    self._persist(cursor)
                continue
            attempted += 1
            try:
                self._sink.emit(entry.record, seq=entry.seq)
            except ExportError as exc:
                self._persist(cursor)
                return ExportReport(
                    exported=exported,
                    attempted=attempted,
                    last_seq=cursor,
                    error=str(exc),
                    reset=reset,
                )
            exported += 1
            cursor = entry.seq
            self._persist(cursor)
        return ExportReport(exported=exported, attempted=attempted, last_seq=cursor, reset=reset)
