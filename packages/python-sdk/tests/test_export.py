"""Tests for the OTLP export orchestrator (M5 5.1/5.3, R4).

The exporter turns stored :class:`~agentwatch.records.AgentRecord` objects into
OpenTelemetry spans and forwards them through an injected sink. These tests use
the SDK's in-memory exporter so the span shape is asserted without a network.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from agentwatch.attrs import (
    GEN_AI_AGENT_NAME,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_OPERATION_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_TOOL_NAME,
    SPAN_KIND_TOOL,
)
from agentwatch.export import ExportOrchestrator, OTelSpanSink, record_to_attributes
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore


def _record(
    name: str = "Bash",
    *,
    session: str = "sess-1",
    outcome: Outcome = Outcome.OK,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent", name="agent"),
        tool=ToolCall(name=name),
        outcome=outcome,
        started_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        ended_at=datetime(2026, 1, 2, 3, 4, 6, tzinfo=timezone.utc),
        trace_id=session,
        span_id="a" * 16,
        step_type=None,
    )


def _sink() -> tuple[OTelSpanSink, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    return OTelSpanSink(provider, exporter=exporter), exporter


def test_otel_sink_emits_an_execute_tool_span() -> None:
    sink, exporter = _sink()

    sink.emit(_record(), seq=0)

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "Bash"
    assert span.attributes[GEN_AI_OPERATION_NAME] == SPAN_KIND_TOOL
    assert span.attributes[GEN_AI_TOOL_NAME] == "Bash"
    assert span.attributes[GEN_AI_CONVERSATION_ID] == "sess-1"
    assert span.attributes["agentwatch.seq"] == 0


def test_otel_sink_maps_outcome_to_span_status() -> None:
    sink, exporter = _sink()

    sink.emit(_record("Bash", outcome=Outcome.OK), seq=0)
    sink.emit(_record("Bash", outcome=Outcome.ERROR), seq=1)
    sink.emit(_record("Bash", outcome=Outcome.DENIED), seq=2)

    statuses = [span.status.status_code for span in exporter.get_finished_spans()]
    assert statuses == [StatusCode.UNSET, StatusCode.ERROR, StatusCode.ERROR]


def test_orchestrator_exports_every_record_in_order(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("first"))
    store.append(_record("second"))
    sink, exporter = _sink()

    report = ExportOrchestrator(store, sink).export_pending()

    assert report.exported == 2
    assert report.attempted == 2
    assert report.last_seq == 1
    assert report.error is None
    assert [span.name for span in exporter.get_finished_spans()] == ["first", "second"]


def test_orchestrator_on_empty_store_reports_nothing(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    sink, exporter = _sink()

    report = ExportOrchestrator(store, sink).export_pending()

    assert report.exported == 0
    assert report.attempted == 0
    assert report.last_seq == -1
    assert exporter.get_finished_spans() == ()


def test_record_to_attributes_maps_every_correlation_dimension() -> None:
    record = AgentRecord(
        session_id="sess-1",
        agent=AgentIdentity(
            identity="agent",
            name="named",
            version="1.2.3",
            model_version="claude-3",
            workload_type="triage",
        ),
        tool=ToolCall(name="Bash", server="mcp-shell"),
        outcome=Outcome.OK,
        started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        harness="claude-code",
        duration_ms=12.5,
        tokens=42,
        cost_usd=0.01,
    )

    attributes = record_to_attributes(record, seq=7)

    assert attributes[GEN_AI_AGENT_NAME] == "named"
    assert attributes["gen_ai.agent.version"] == "1.2.3"
    assert attributes[GEN_AI_REQUEST_MODEL] == "claude-3"
    assert attributes["gen_ai.agent.workload.type"] == "triage"
    assert attributes["mcp.server"] == "mcp-shell"
    assert attributes["agentwatch.harness"] == "claude-code"
    assert attributes["agentwatch.duration_ms"] == 12.5
    assert attributes["gen_ai.usage.total_tokens"] == 42
    assert attributes["gen_ai.agent.run.cost.total"] == 0.01
    assert attributes["agentwatch.seq"] == 7


def test_record_to_attributes_falls_back_to_identity_for_the_agent_name() -> None:
    record = AgentRecord(
        session_id="sess-1",
        agent=AgentIdentity(identity="only-identity"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    assert record_to_attributes(record, seq=0)[GEN_AI_AGENT_NAME] == "only-identity"


def test_otel_sink_preserves_valid_hex_ids_and_hashes_others() -> None:
    sink, exporter = _sink()
    valid = AgentRecord(
        session_id="sess-1",
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        trace_id="1" * 32,
        span_id="2" * 16,
        parent_span_id="3" * 16,
    )
    hashed = AgentRecord(
        session_id="sess-2",
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        trace_id="not-hex-at-all-but-long-enough",
        span_id="z" * 16,
        parent_span_id="z" * 16,
    )

    sink.emit(valid, seq=0)
    sink.emit(hashed, seq=1)

    spans = exporter.get_finished_spans()
    assert spans[0].context.trace_id == int("1" * 32, 16)
    assert spans[0].parent.span_id == int("3" * 16, 16)
    # Non-hex -> hashed deterministically; the two records stay in distinct traces.
    assert spans[1].context.trace_id != spans[0].context.trace_id


def test_records_in_a_session_share_one_trace(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("first"))
    store.append(_record("second"))
    sink, exporter = _sink()

    ExportOrchestrator(store, sink).export_pending()

    traces = {span.context.trace_id for span in exporter.get_finished_spans()}
    assert len(traces) == 1


def test_orchestrator_skips_tombstoned_records(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("old"))
    store.append(_record("fresh"))
    store.apply_retention(retention_days=0, now=datetime(2030, 1, 1, tzinfo=timezone.utc))
    sink, exporter = _sink()

    report = ExportOrchestrator(store, sink).export_pending()

    names = [span.name for span in exporter.get_finished_spans()]
    assert names == []
    assert report.attempted == 0
    assert report.last_seq == -1
