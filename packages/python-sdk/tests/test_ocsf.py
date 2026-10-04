"""OCSF + CloudEvents mapping tests (M20 S8, #260)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from agentwatch.cli.main import main
from agentwatch.ocsf import (
    CLOUDEVENTS_VERSION,
    MAPPING_TABLE,
    OCSF_VERSION,
    ocsf_target,
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


def _event(kind: SecurityEventType, **kwargs: Any) -> SecurityEvent:
    return SecurityEvent(type=kind, emitted_at=AT, emitter="agentwatch", **kwargs)


def test_every_shipped_event_type_is_mapped() -> None:
    for member in SecurityEventType:
        assert ocsf_target(member.value) is not None, member.value


def test_denied_maps_to_ocsf_authorize() -> None:
    event = _event(SecurityEventType.DENIED, tool="Bash", reason="refused")

    obj = to_ocsf(event, session_id="s1", seq=3)

    assert obj["class_uid"] == 3003
    assert obj["class_name"] == "Authorize"
    assert obj["activity_name"] == "Deny"
    assert obj["metadata"]["version"] == OCSF_VERSION
    assert obj["type_uid"] == 3003 * 100 + 2
    assert obj["message"] == "refused"
    # Fields OCSF cannot express are preserved, never dropped.
    assert obj["unmapped"]["event_version"] == "0.1.0"
    assert obj["unmapped"]["tool"] == "Bash"
    assert obj["unmapped"]["session_id"] == "s1"


def test_evidence_is_preserved_in_unmapped() -> None:
    event = _event(SecurityEventType.SECRET_DETECTED, evidence={"kinds": ["api-key"]})
    obj = to_ocsf(event)
    assert obj["unmapped"]["evidence"] == {"kinds": ["api-key"]}


def test_unmapped_type_is_exported_explicitly() -> None:
    removed = MAPPING_TABLE.pop("halted")
    try:
        obj = to_ocsf(_event(SecurityEventType.HALTED))
    finally:
        MAPPING_TABLE["halted"] = removed

    assert obj["unmapped_type"] is True
    assert obj["type_uid"] == 0
    assert obj["unmapped"]["event_type"] == "halted"


def test_cloudevents_envelope_shape() -> None:
    event = _event(SecurityEventType.POLICY_FIRED, policy_id="p1")

    envelope = to_cloudevents(event, session_id="s1", seq=1)

    assert envelope["specversion"] == CLOUDEVENTS_VERSION
    assert envelope["source"] == "agentwatch"
    assert envelope["type"] == "io.agentwatch.security-event.policy-fired"
    assert envelope["subject"] == "s1"
    assert envelope["data"]["policy_id"] == "p1"
    assert envelope["id"]


def _record_with(event: SecurityEvent) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.DENIED,
        started_at=AT,
        step_type=StepType.OBSERVE,
        security_event=event,
    )


def test_cli_export_session_ocsf(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    store.append(_record_with(_event(SecurityEventType.DENIED, tool="Bash")))

    rc = main(["--set", f"store.path={store_dir}", "export-session", "s1", "--format", "ocsf"])

    assert rc == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["class_name"] == "Authorize"


def test_cli_export_session_cloudevents(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    store.append(_record_with(_event(SecurityEventType.HALTED)))

    rc = main(
        ["--set", f"store.path={store_dir}", "export-session", "s1", "--format", "cloudevents"]
    )

    assert rc == 0
    line = capsys.readouterr().out.strip()
    assert json.loads(line)["specversion"] == "1.0"
