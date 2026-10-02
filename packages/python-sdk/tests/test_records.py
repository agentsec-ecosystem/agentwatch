"""Tests for the agentwatch record and security-event models (M2, #16/#17).

The model is the Python form of the normative contract in ``schema/``: it must
round-trip losslessly and carry exactly the documented fields.
"""

from __future__ import annotations

from datetime import datetime, timezone

from agentwatch.records import (
    EVENT_VERSION,
    SCHEMA_VERSION,
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    SecurityEvent,
    SecurityEventType,
    StepType,
    ToolCall,
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


def test_enums_match_the_schema() -> None:
    assert [o.value for o in Outcome] == ["ok", "error", "denied"]
    assert [s.value for s in StepType] == ["reason", "act", "observe", "verify"]
    assert [p.value for p in RecordPrivacyMode] == [
        "metadata-only",
        "truncated",
        "hashed",
        "full",
    ]
    assert [e.value for e in SecurityEventType] == [
        "denied",
        "policy-fired",
        "secret-detected",
        "revoked",
        "halted",
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
