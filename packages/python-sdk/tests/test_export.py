"""Tests for the OTLP export orchestrator (M5 5.1/5.3, R4).

The exporter turns stored :class:`~agentwatch.records.AgentRecord` objects into
OpenTelemetry spans and forwards them through an injected sink. These tests use
the SDK's in-memory exporter so the span shape is asserted without a network.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
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
from agentwatch.export import (
    ExportError,
    ExportOrchestrator,
    ExportState,
    ExportWatermark,
    OTelSpanSink,
    _TrackingExporter,
    record_to_attributes,
)
from agentwatch.records import (
    EVENT_VERSION,
    AgentIdentity,
    AgentRecord,
    Outcome,
    SecurityEvent,
    SecurityEventType,
    ToolCall,
)
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
    assert span.attributes is not None
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
    assert spans[0].parent is not None
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


def _event_record() -> AgentRecord:
    event = SecurityEvent(
        type=SecurityEventType.SECRET_DETECTED,
        emitted_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        emitter="agentwatch",
        tool="Bash",
        reason="detected",
        policy_id="p-1",
        credential_ref="cred-1",
        evidence={"kinds": ["api-key"]},
    )
    base = _record()
    return replace(base, security_event=event)


def test_security_event_is_exported_as_a_span_event() -> None:
    sink, exporter = _sink()

    sink.emit(_event_record(), seq=0)

    span = exporter.get_finished_spans()[0]
    assert len(span.events) == 1
    event = span.events[0]
    assert event.attributes is not None
    assert event.name == SecurityEventType.SECRET_DETECTED.value
    assert event.attributes["emitter"] == "agentwatch"
    assert event.attributes["reason"] == "detected"
    assert event.attributes["policy_id"] == "p-1"
    assert event.attributes["credential_ref"] == "cred-1"
    assert event.attributes["event_version"] == EVENT_VERSION
    assert event.attributes["evidence"] == '{"kinds": ["api-key"]}'


def test_record_without_a_security_event_has_no_span_events() -> None:
    sink, exporter = _sink()

    sink.emit(_record(), seq=0)

    assert exporter.get_finished_spans()[0].events == ()

    minimal = SecurityEvent(
        type=SecurityEventType.HALTED,
        emitted_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    sink.emit(replace(_record(), security_event=minimal), seq=1)

    event = exporter.get_finished_spans()[1].events[0]
    assert event.attributes is not None
    assert event.name == "halted"
    assert set(event.attributes) == {"event_version"}


def test_orchestrator_forwards_security_events_for_each_record(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_event_record())
    store.append(_record("plain"))
    sink, exporter = _sink()

    ExportOrchestrator(store, sink).export_pending()

    spans = exporter.get_finished_spans()
    assert [len(span.events) for span in spans] == [1, 0]


def test_export_is_blocked_when_the_self_test_fails(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    sink, exporter = _sink()

    report = ExportOrchestrator(store, sink, self_test=lambda: False).export_pending()

    assert report.blocked is True
    assert report.exported == 0
    assert report.attempted == 0
    assert exporter.get_finished_spans() == ()


def test_export_proceeds_when_the_self_test_passes(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    sink, exporter = _sink()

    report = ExportOrchestrator(store, sink, self_test=lambda: True).export_pending()

    assert report.blocked is False
    assert report.exported == 1
    assert len(exporter.get_finished_spans()) == 1


def test_default_gate_uses_the_redaction_self_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    sink, exporter = _sink()
    monkeypatch.setattr("agentwatch.export.export_allowed", lambda: False)

    report = ExportOrchestrator(store, sink).export_pending()

    assert report.blocked is True
    assert exporter.get_finished_spans() == ()


class _FailingSink:
    """A sink that rejects the record at ``fail_at`` and counts attempts."""

    def __init__(self, fail_at: int) -> None:
        self.fail_at = fail_at
        self.seen: list[int] = []

    def emit(self, record: AgentRecord, *, seq: int) -> None:
        if seq == self.fail_at:
            raise ExportError("endpoint down")
        self.seen.append(seq)


def test_endpoint_failure_keeps_local_records_and_stops(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("first"))
    store.append(_record("second"))
    store.append(_record("third"))
    sink = _FailingSink(fail_at=1)

    report = ExportOrchestrator(store, sink).export_pending()

    assert report.exported == 1
    assert report.attempted == 2
    assert report.last_seq == 0
    assert report.error == "endpoint down"
    # F5: no record was lost or removed locally; the third was never attempted.
    assert [record.tool.name for record in store.records()] == ["first", "second", "third"]
    assert sink.seen == [0]


def test_export_resumes_after_the_endpoint_recovers(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("first"))
    store.append(_record("second"))
    failing = _FailingSink(fail_at=1)

    first = ExportOrchestrator(store, failing).export_pending()
    recovered = _RecordingSink()
    second = ExportOrchestrator(store, recovered).export_pending()

    assert first.exported == 1
    # The cursor resumes past the last delivered record: no double-export.
    assert second.exported == 1
    assert recovered.seen == [1]
    assert [record.tool.name for record in store.records()] == ["first", "second"]


class _RecordingSink:
    def __init__(self) -> None:
        self.seen: list[int] = []

    def emit(self, record: AgentRecord, *, seq: int) -> None:
        self.seen.append(seq)


class _FailingExporter(SpanExporter):
    def export(self, spans: Any) -> SpanExportResult:
        return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def test_otel_sink_raises_when_the_exporter_reports_failure() -> None:
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    sink = OTelSpanSink(provider, exporter=_FailingExporter())

    with pytest.raises(ExportError):
        sink.emit(_record(), seq=0)


def test_orchestrator_surfaces_a_failing_otel_exporter(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    sink = OTelSpanSink(provider, exporter=_FailingExporter())

    report = ExportOrchestrator(store, sink).export_pending()

    assert report.exported == 0
    assert report.error is not None
    assert store.records() != []


def test_tracking_exporter_delegates_lifecycle() -> None:
    inner = InMemorySpanExporter()
    tracker = _TrackingExporter(inner)

    assert tracker.force_flush() is True
    tracker.shutdown()
    assert tracker.last_result is SpanExportResult.SUCCESS


def test_export_state_round_trips_a_watermark(tmp_path: Path) -> None:
    state = ExportState(tmp_path / "export.state.json")
    stamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    state.save(ExportWatermark(last_seq=4, updated_at=stamp))

    assert state.load() == ExportWatermark(last_seq=4, updated_at=stamp)


def test_export_state_defaults_when_missing_or_corrupt(tmp_path: Path) -> None:
    state = ExportState(tmp_path / "export.state.json")
    assert state.load() == ExportWatermark()

    state.path.write_text("{ not json", encoding="utf-8")
    assert state.load() == ExportWatermark()


def test_export_state_reset_clears_the_cursor(tmp_path: Path) -> None:
    state = ExportState(tmp_path / "export.state.json")
    state.save(ExportWatermark(last_seq=9, updated_at=datetime.now(timezone.utc)))

    state.reset()

    assert state.load() == ExportWatermark()


def test_export_state_from_store_sits_beside_the_store(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")

    state = ExportState.from_store(store)

    assert state.path == tmp_path / "export.state.json"


def test_cursor_prevents_double_export(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("first"))
    store.append(_record("second"))
    state = ExportState(tmp_path / "export.state.json")
    sink, _ = _sink()

    first = ExportOrchestrator(store, sink, state=state).export_pending()
    again, again_exporter = _sink()
    second = ExportOrchestrator(store, again, state=state).export_pending()

    assert first.exported == 2
    assert first.last_seq == 1
    assert second.exported == 0
    assert again_exporter.get_finished_spans() == ()


def test_cursor_resumes_with_only_new_records(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("first"))
    state = ExportState(tmp_path / "export.state.json")
    ExportOrchestrator(store, _sink()[0], state=state).export_pending()

    store.append(_record("second"))
    sink, exporter = _sink()
    report = ExportOrchestrator(store, sink, state=state).export_pending()

    assert report.exported == 1
    assert [span.name for span in exporter.get_finished_spans()] == ["second"]


def test_cursor_persists_across_a_fresh_state_object(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("first"))
    ExportOrchestrator(
        store, _sink()[0], state=ExportState(tmp_path / "export.state.json")
    ).export_pending()

    restarted = ExportState(tmp_path / "export.state.json")
    report = ExportOrchestrator(
        store, _RecordingSink(), state=restarted
    ).export_pending()

    assert report.exported == 0


def test_repaired_store_resets_the_cursor_with_notice(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("only"))
    state = ExportState(tmp_path / "export.state.json")
    state.save(ExportWatermark(last_seq=99, updated_at=datetime.now(timezone.utc)))
    sink, exporter = _sink()

    report = ExportOrchestrator(store, sink, state=state).export_pending()

    assert report.reset is True
    assert report.exported == 1
    assert [span.name for span in exporter.get_finished_spans()] == ["only"]
    assert state.load().last_seq == 0


def test_blocked_export_reports_the_current_position(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    state = ExportState(tmp_path / "export.state.json")
    state.save(ExportWatermark(last_seq=0, updated_at=datetime.now(timezone.utc)))

    report = ExportOrchestrator(
        store, _RecordingSink(), state=state, self_test=lambda: False
    ).export_pending()

    assert report.blocked is True
    assert report.last_seq == 0
    assert state.load().last_seq == 0


def test_cursor_advances_past_tombstoned_records(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("old"))
    store.append(_record("fresh", session="other"))
    store.apply_retention(retention_days=0, now=datetime(2030, 1, 1, tzinfo=timezone.utc))
    state = ExportState(tmp_path / "export.state.json")
    sink, _ = _sink()

    report = ExportOrchestrator(store, sink, state=state).export_pending()

    assert report.attempted == 0
    assert state.load().last_seq == 1
