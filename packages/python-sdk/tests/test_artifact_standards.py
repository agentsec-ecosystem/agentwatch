"""Open artifact standards conformance (M22 W3, #272)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agentwatch.bom import CYCLONEDX_SPEC_VERSION, build_bom, to_cyclonedx, validate_cyclonedx
from agentwatch.ocsf import (
    CLOUDEVENTS_VERSION,
    OCSF_VERSION,
    to_cloudevents,
    to_ocsf,
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


def _event() -> SecurityEvent:
    return SecurityEvent(
        type=SecurityEventType.DENIED, emitted_at=AT, emitter="claude-code", tool="Bash"
    )


def test_ocsf_output_pins_its_version() -> None:
    obj = to_ocsf(_event(), session_id="s1")
    assert obj["metadata"]["version"] == OCSF_VERSION


def test_cloudevents_output_pins_its_version() -> None:
    envelope = to_cloudevents(_event(), session_id="s1")
    assert envelope["specversion"] == CLOUDEVENTS_VERSION


def test_cyclonedx_output_validates_against_pinned_spec(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        AgentRecord(
            session_id="s1",
            agent=AgentIdentity(identity="a", name="claude"),
            tool=ToolCall(name="Bash"),
            outcome=Outcome.OK,
            started_at=AT,
            step_type=StepType.ACT,
        )
    )

    document = to_cyclonedx(build_bom(store))

    assert document["bomFormat"] == "CycloneDX"
    assert document["specVersion"] == CYCLONEDX_SPEC_VERSION
    assert validate_cyclonedx(document) == []


def test_unmapped_fields_are_reported_not_dropped() -> None:
    obj = to_ocsf(_event(), session_id="s1")
    assert "unmapped" in obj
    assert obj["unmapped"]["tool"] == "Bash"
