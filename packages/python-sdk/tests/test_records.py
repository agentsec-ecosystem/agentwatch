"""Tests for the agentwatch record and security-event models (M2, #16/#17).

The model is the Python form of the normative contract in ``schema/``: it must
round-trip losslessly and carry exactly the documented fields.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

import pytest

from agentwatch.records import (
    EVENT_VERSION,
    SCHEMA_VERSION,
    SUPPORTED_EVENT_VERSIONS,
    SUPPORTED_SCHEMA_VERSIONS,
    AgentIdentity,
    AgentRecord,
    CredentialClass,
    Outcome,
    RecordPhase,
    RecordPrivacyMode,
    RecordValidationError,
    SecurityEvent,
    SecurityEventType,
    StepType,
    ToolCall,
    effective_record_phase,
    validate_event,
    validate_record,
)

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
END = datetime(2026, 1, 2, 3, 4, 5, 120000, tzinfo=timezone.utc)


def _record(**overrides: object) -> AgentRecord:
    base: dict[str, object] = {
        "session_id": "sess-1",
        "agent": AgentIdentity(identity="agent-1", name="triage", version="1.0"),
        "tool": ToolCall(
            name="Bash",
            server="mcp-bash",
            arguments={"cmd": "ls"},
            privacy_mode=RecordPrivacyMode.TRUNCATED,
        ),
        "outcome": Outcome.OK,
        "started_at": START,
        "harness": "claude-code",
        "trace_id": "trace-1",
        "span_id": "span-1",
        "ended_at": END,
        "duration_ms": 12.5,
        "tokens": 42,
        "cost_usd": 0.001,
        "step_type": StepType.ACT,
    }
    base.update(overrides)
    return AgentRecord(**base)  # type: ignore[arg-type]


def test_version_constants() -> None:
    assert SCHEMA_VERSION == "0.1.0"
    assert EVENT_VERSION == "0.1.0"
    assert SUPPORTED_SCHEMA_VERSIONS == ("0.1.0", "0.2.0")
    assert SUPPORTED_EVENT_VERSIONS == ("0.1.0", "0.2.0")


def test_enums_match_the_schema() -> None:
    assert [o.value for o in Outcome] == ["ok", "error", "denied"]
    assert [s.value for s in StepType] == ["reason", "act", "observe", "verify"]
    assert [p.value for p in RecordPrivacyMode] == [
        "metadata-only",
        "truncated",
        "hashed",
        "full",
    ]
    assert [p.value for p in RecordPhase] == [
        "pre_execution",
        "post_execution",
        "unknown",
    ]
    assert [c.value for c in CredentialClass] == [
        "api-key",
        "oauth",
        "svid",
        "ambient/shared",
    ]
    assert [e.value for e in SecurityEventType] == [
        "denied",
        "policy-fired",
        "secret-detected",
        "revoked",
        "halted",
        "drift-detected",
        "tool-surface-changed",
        "agent-delegation",
        "recorder-config-changed",
        "mode-transition",
        "sandbox-boundary",
        "capability-changed",
    ]


def test_to_dict_shape() -> None:
    data = _record().to_dict()

    assert data["schema_version"] == "0.1.0"
    assert data["session_id"] == "sess-1"
    assert data["harness"] == "claude-code"
    assert data["agent"] == {"identity": "agent-1", "name": "triage", "version": "1.0"}
    assert data["tool"] == {
        "name": "Bash",
        "server": "mcp-bash",
        "arguments": {"cmd": "ls"},
        "privacy_mode": "truncated",
    }
    assert data["outcome"] == "ok"
    assert data["started_at"] == "2026-01-02T03:04:05+00:00"
    assert data["ended_at"] == "2026-01-02T03:04:05.120000+00:00"
    assert data["step_type"] == "act"
    assert data["duration_ms"] == 12.5
    assert data["tokens"] == 42


def test_round_trip_is_lossless() -> None:
    record = _record()
    assert AgentRecord.from_dict(record.to_dict()) == record


def test_unset_optionals_are_omitted() -> None:
    minimal = AgentRecord(
        session_id="s",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name="t"),
        outcome=Outcome.DENIED,
        started_at=START,
    )
    data = minimal.to_dict()

    assert data["schema_version"] == "0.1.0"
    assert "trace_id" not in data
    assert "ended_at" not in data
    assert "duration_ms" not in data
    assert "step_type" not in data
    assert "record_phase" not in data
    assert "traceparent" not in data
    assert "security_event" not in data


def test_security_event_round_trip() -> None:
    event = SecurityEvent(
        type=SecurityEventType.DENIED,
        emitted_at=START,
        emitter="agentpolicy",
        reason="blocked by policy",
        policy_id="pol-1",
        tool="Bash",
    )
    data = event.to_dict()

    assert data["event_version"] == "0.1.0"
    assert data["type"] == "denied"
    assert data["emitted_at"] == "2026-01-02T03:04:05+00:00"
    assert SecurityEvent.from_dict(data) == event


def test_record_carries_nested_security_event() -> None:
    event = SecurityEvent(type=SecurityEventType.HALTED, emitted_at=START, emitter="agenthalt")
    record = _record(outcome=Outcome.DENIED, security_event=event)

    data = record.to_dict()
    assert data["security_event"]["type"] == "halted"
    assert AgentRecord.from_dict(data) == record


# ---------------------------------------------------------------------------
# Validation (M2 2.3/2.4): reject, never coerce
# ---------------------------------------------------------------------------


def _valid_dict() -> dict[str, Any]:
    return _record().to_dict()


def _valid_event_dict() -> dict[str, Any]:
    return SecurityEvent(
        type=SecurityEventType.DENIED,
        emitted_at=START,
        emitter="agentpolicy",
        reason="blocked",
    ).to_dict()


def test_validate_record_returns_the_model() -> None:
    assert validate_record(_valid_dict()) == _record()


def test_validate_event_returns_the_model() -> None:
    event = validate_event(_valid_event_dict())
    assert event.type is SecurityEventType.DENIED
    assert event.emitter == "agentpolicy"


@pytest.mark.parametrize(
    "key",
    ["schema_version", "session_id", "agent", "tool", "outcome", "started_at"],
)
def test_missing_required_record_field_is_rejected(key: str) -> None:
    data = _valid_dict()
    del data[key]
    with pytest.raises(RecordValidationError, match=key):
        validate_record(data)


@pytest.mark.parametrize("key", ["event_version", "type", "emitted_at"])
def test_missing_required_event_field_is_rejected(key: str) -> None:
    data = _valid_event_dict()
    del data[key]
    with pytest.raises(RecordValidationError, match=key):
        validate_event(data)


@pytest.mark.parametrize(
    "path,key",
    [
        ((), "surprise"),
        (("agent",), "surprise"),
        (("tool",), "surprise"),
        (("security_event",), "surprise"),
    ],
)
def test_unknown_keys_are_rejected(path: tuple[str, ...], key: str) -> None:
    data = _valid_dict()
    data["security_event"] = _valid_event_dict()
    node = data
    for step in path:
        node = node[step]
    node[key] = 1
    with pytest.raises(RecordValidationError, match=key):
        validate_record(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("duration_ms", "5s"),
        ("tokens", 1.5),
        ("tokens", True),
        ("duration_ms", True),
        ("started_at", 123),
        ("harness", 5),
    ],
)
def test_wrong_types_are_rejected_not_coerced(field: str, value: object) -> None:
    data = _valid_dict()
    data[field] = value
    with pytest.raises(RecordValidationError, match=field):
        validate_record(data)


def test_wrong_nested_types_are_rejected() -> None:
    data = _valid_dict()
    data["tool"]["arguments"] = ["not", "a", "dict"]
    with pytest.raises(RecordValidationError, match="arguments"):
        validate_record(data)

    data = _valid_dict()
    data["agent"] = "not-a-table"
    with pytest.raises(RecordValidationError, match="agent"):
        validate_record(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("outcome", "maybe"),
        ("step_type", "ponder"),
    ],
)
def test_bad_record_enum_is_rejected(field: str, value: str) -> None:
    data = _valid_dict()
    data[field] = value
    with pytest.raises(RecordValidationError, match=field):
        validate_record(data)


def test_bad_tool_privacy_mode_is_rejected() -> None:
    data = _valid_dict()
    data["tool"]["privacy_mode"] = "nope"
    with pytest.raises(RecordValidationError, match="privacy_mode"):
        validate_record(data)


def test_bad_event_type_is_rejected() -> None:
    data = _valid_event_dict()
    data["type"] = "exploded"
    with pytest.raises(RecordValidationError, match="type"):
        validate_event(data)


def test_unknown_schema_version_is_rejected() -> None:
    data = _valid_dict()
    data["schema_version"] = "9.9.9"
    with pytest.raises(RecordValidationError, match="9.9.9"):
        validate_record(data)


def test_unknown_event_version_is_rejected() -> None:
    data = _valid_event_dict()
    data["event_version"] = "9.9.9"
    with pytest.raises(RecordValidationError, match="9.9.9"):
        validate_event(data)


def test_nullable_fields_accept_null_and_omission() -> None:
    data = _valid_dict()
    data["parent_span_id"] = None
    data["ended_at"] = None
    data["step_type"] = None
    validate_record(data)

    omitted = _valid_dict()
    omitted.pop("parent_span_id", None)
    validate_record(omitted)


def test_nullable_numeric_fields_accept_null() -> None:
    # schema types duration_ms/tokens/cost_usd as ["number"/"integer","null"].
    data = _valid_dict()
    data["duration_ms"] = None
    data["tokens"] = None
    data["cost_usd"] = None
    validate_record(data)


def test_non_table_input_is_rejected() -> None:
    with pytest.raises(RecordValidationError):
        validate_record(["not", "a", "table"])


def test_record_validation_is_pure() -> None:
    # validate_record must not mutate the caller's mapping (no coercion in place).
    data = _valid_dict()
    original = copy.deepcopy(data)
    validate_record(data)
    assert data == original


def _record_with_response(response: Any) -> AgentRecord:
    return AgentRecord(
        session_id="s",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name="Bash", response=response),
        outcome=Outcome.OK,
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_tool_response_round_trips() -> None:
    record = _record_with_response({"output": "ok"})

    data = record.to_dict()

    assert data["tool"]["response"] == {"output": "ok"}
    assert AgentRecord.from_dict(data) == record
    validate_record(data)


def test_tool_response_must_be_an_object() -> None:
    data = _record_with_response({"output": "ok"}).to_dict()
    data["tool"]["response"] = "not-an-object"

    with pytest.raises(RecordValidationError):
        validate_record(data)


# ---------------------------------------------------------------------------
# M9: additive project / parent-session fields (PRD 25 I3/I4)
# ---------------------------------------------------------------------------


def test_new_optional_fields_round_trip() -> None:
    record = _record(project="/repo/a", parent_session_id="sess-parent")
    data = record.to_dict()

    assert data["project"] == "/repo/a"
    assert data["parent_session_id"] == "sess-parent"
    assert AgentRecord.from_dict(data) == record
    assert validate_record(data) == record


def test_legacy_record_without_new_fields_round_trips() -> None:
    data = _record().to_dict()

    assert "project" not in data
    assert "parent_session_id" not in data
    assert validate_record(data) == _record()


def test_new_fields_reject_wrong_types() -> None:
    data = _valid_dict()
    data["project"] = 5
    with pytest.raises(RecordValidationError, match="project"):
        validate_record(data)

    data = _valid_dict()
    data["parent_session_id"] = ["not", "a", "string"]
    with pytest.raises(RecordValidationError, match="parent_session_id"):
        validate_record(data)


def test_new_fields_accept_null_and_omission() -> None:
    data = _valid_dict()
    data["project"] = None
    data["parent_session_id"] = None
    validate_record(data)


def test_host_round_trips_and_is_dropped_when_none() -> None:
    data = _valid_dict()
    data["host"] = "runner-1"
    record = validate_record(data)
    assert record.host == "runner-1"
    assert record.to_dict()["host"] == "runner-1"
    assert validate_record(record.to_dict()) == record
    assert "host" not in _record().to_dict()


def test_host_rejects_wrong_type() -> None:
    data = _valid_dict()
    data["host"] = 5
    with pytest.raises(RecordValidationError, match="host"):
        validate_record(data)


def test_drift_detected_event_validates() -> None:
    event = validate_event(
        {
            "event_version": EVENT_VERSION,
            "type": "drift-detected",
            "emitted_at": "2026-01-02T03:04:05+00:00",
            "emitter": "agentwatch",
            "evidence": {"metric": "errors", "z_score": 4.1},
        }
    )
    assert event.type is SecurityEventType.DRIFT_DETECTED


# ---------------------------------------------------------------------------
# v0.2.0 SCHEMA-1: additive AAT/identity fields + supported version range
# ---------------------------------------------------------------------------


def test_record_phase_and_traceparent_round_trip() -> None:
    record = _record(
        record_phase=RecordPhase.PRE_EXECUTION,
        traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    )
    data = record.to_dict()

    assert data["record_phase"] == "pre_execution"
    assert data["traceparent"] == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    assert AgentRecord.from_dict(data) == record
    assert validate_record(data) == record


def test_legacy_record_reads_as_unknown_phase() -> None:
    record = _record()
    assert record.record_phase is None
    assert effective_record_phase(record) is RecordPhase.UNKNOWN
    assert effective_record_phase(_record(record_phase=RecordPhase.POST_EXECUTION)) is (
        RecordPhase.POST_EXECUTION
    )


def test_agent_identity_dimension_round_trips() -> None:
    agent = AgentIdentity(
        identity="agent-1",
        name="triage",
        workload_identity="spiffe://corp.example/agent/triage",
        credential_class=CredentialClass.SVID,
        principal="sha256:abc123",
        delegation_chain=("sha256:user", "sha256:agent"),
    )
    record = _record(agent=agent)
    data = record.to_dict()

    assert data["agent"]["workload_identity"] == "spiffe://corp.example/agent/triage"
    assert data["agent"]["credential_class"] == "svid"
    assert data["agent"]["principal"] == "sha256:abc123"
    assert data["agent"]["delegation_chain"] == ["sha256:user", "sha256:agent"]
    assert AgentRecord.from_dict(data) == record
    assert validate_record(data) == record


def test_identity_dimension_defaults_omitted() -> None:
    data = _record().to_dict()
    assert "workload_identity" not in data["agent"]
    assert "credential_class" not in data["agent"]
    assert "principal" not in data["agent"]
    assert "delegation_chain" not in data["agent"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("record_phase", "during"),
        ("traceparent", 5),
    ],
)
def test_bad_new_record_fields_are_rejected(field: str, value: object) -> None:
    data = _valid_dict()
    data[field] = value
    with pytest.raises(RecordValidationError, match=field):
        validate_record(data)


def test_bad_identity_fields_are_rejected() -> None:
    data = _valid_dict()
    data["agent"]["credential_class"] = "magic"
    with pytest.raises(RecordValidationError, match="credential_class"):
        validate_record(data)

    data = _valid_dict()
    data["agent"]["delegation_chain"] = "not-a-list"
    with pytest.raises(RecordValidationError, match="delegation_chain"):
        validate_record(data)

    data = _valid_dict()
    data["agent"]["delegation_chain"] = ["ok", 5]
    with pytest.raises(RecordValidationError, match="delegation_chain"):
        validate_record(data)


def test_supported_schema_versions_are_accepted() -> None:
    for version in SUPPORTED_SCHEMA_VERSIONS:
        data = _valid_dict()
        data["schema_version"] = version
        assert validate_record(data).schema_version == version


def test_unsupported_schema_version_names_the_range() -> None:
    data = _valid_dict()
    data["schema_version"] = "9.9.9"
    with pytest.raises(RecordValidationError, match="0.2.0"):
        validate_record(data)


def test_agent_delegation_event_validates() -> None:
    event = validate_event(
        {
            "event_version": EVENT_VERSION,
            "type": "agent-delegation",
            "emitted_at": "2026-01-02T03:04:05+00:00",
            "emitter": "agentwatch",
            "evidence": {"from": "agent-a", "to": "agent-b"},
        }
    )
    assert event.type is SecurityEventType.AGENT_DELEGATION
