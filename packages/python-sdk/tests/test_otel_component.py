"""OTel collector component mapping tests (M20 S39, #262)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agentwatch.attrs import GEN_AI_TOOL_NAME
from agentwatch.otel_component import (
    SEMCONV_VERSION,
    collect_spans,
    component_manifest,
    receiver_status,
    record_to_span,
    resource_attributes,
)
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    SecurityEvent,
    SecurityEventType,
    StepType,
    ToolCall,
)
from agentwatch.store import RecordStore

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record() -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="a", name="claude"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.DENIED,
        started_at=AT,
        step_type=StepType.OBSERVE,
        security_event=SecurityEvent(
            type=SecurityEventType.DENIED, emitted_at=AT, emitter="claude-code", tool="Bash"
        ),
    )


def test_record_maps_to_semconv_span() -> None:
    span = record_to_span(_record(), 3)

    assert span.name == "Bash"
    assert span.attributes[GEN_AI_TOOL_NAME] == "Bash"
    assert span.trace_id and span.span_id
    assert len(span.events) == 1
    assert span.events[0]["name"] == "denied"


def test_resource_attributes_carry_pinned_version() -> None:
    assert resource_attributes()["otel.semconv.version"] == SEMCONV_VERSION


def test_collect_spans_from_store(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())

    spans = collect_spans(store)

    assert len(spans) == 1
    assert spans[0].to_dict()["name"] == "Bash"


def test_receiver_status_missing_store_is_unavailable(tmp_path: Path) -> None:
    assert receiver_status(tmp_path / "absent.jsonl") == "unavailable"


def test_receiver_status_empty_store_is_unavailable(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    assert receiver_status(store.path) == "unavailable"

    store.append(_record())
    assert receiver_status(store.path) == "ok"


def test_component_manifest() -> None:
    manifest = component_manifest()
    assert manifest["kind"] == "receiver"
    assert manifest["semconv_version"] == SEMCONV_VERSION
