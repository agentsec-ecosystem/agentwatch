"""Pathological-record guard tests (M21 S36, #267)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agentwatch.daemon import Daemon
from agentwatch.guard import RULE_DEPTH, RULE_FIELD_SIZE, RULE_RECORD_SIZE, Limits, guard_record
from agentwatch.receipts import record_receipt
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    StepType,
    ToolCall,
    validate_record,
)
from agentwatch.redact import redaction_config_from_mode

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
BIG = "x" * 5000


def _record(response: dict[str, object] | None) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name="Bash", response=response),
        outcome=Outcome.OK,
        started_at=AT,
        step_type=StepType.OBSERVE,
    )


def test_oversized_field_is_truncated_with_a_marker() -> None:
    guarded = guard_record(
        _record({"out": BIG}), Limits(field_bytes=100, record_bytes=10**9, max_depth=32)
    )

    assert guarded.truncated is not None
    mark = guarded.truncated["fields"][0]
    assert mark["field"] == "tool.response.out"
    assert mark["original_bytes"] == 5000
    assert mark["rule"] == RULE_FIELD_SIZE
    assert guarded.tool.response is not None
    assert str(guarded.tool.response["out"]).endswith("[...]")
    # Still a valid record.
    validate_record(guarded.to_dict())


def test_depth_limit_truncates() -> None:
    nested: dict[str, object] = {"a": {"b": {"c": {"d": 1}}}}
    guarded = guard_record(
        _record(nested), Limits(field_bytes=10**9, record_bytes=10**9, max_depth=2)
    )

    assert guarded.truncated is not None
    assert guarded.truncated["fields"][0]["rule"] == RULE_DEPTH


def test_record_size_limit_drops_content() -> None:
    guarded = guard_record(
        _record({"out": BIG}), Limits(field_bytes=10**9, record_bytes=200, max_depth=32)
    )

    assert guarded.truncated is not None
    assert guarded.truncated["fields"][0]["rule"] == RULE_RECORD_SIZE
    assert guarded.tool.response == {"truncated": RULE_RECORD_SIZE}


def test_small_record_is_untouched() -> None:
    record = _record({"out": "hello"})
    guarded = guard_record(record, Limits())
    assert guarded.truncated is None
    assert guarded == record


def test_receipt_shows_the_truncation_rule() -> None:
    guarded = guard_record(
        _record({"out": BIG}), Limits(field_bytes=100, record_bytes=10**9, max_depth=32)
    )

    receipt = record_receipt(guarded)

    assert "truncation:field-size" in receipt.rules


def test_daemon_applies_limits_on_append(tmp_path: Path) -> None:
    daemon = Daemon(
        socket_path=str(tmp_path / "d.sock"),
        records_path=tmp_path / "records.jsonl",
        redaction=redaction_config_from_mode("truncated"),
        limits=Limits(field_bytes=100, record_bytes=10**9, max_depth=32),
    )
    message = {
        "phase": "post",
        "harness": "claude-code",
        "event": {
            "session_id": "s1",
            "tool_name": "Bash",
            "tool_use_id": "c1",
            "timestamp": AT.isoformat(),
            "tool_response": {"out": BIG},
        },
    }

    records = daemon.handle_message(message)

    truncated = [r for r in records if r.truncated is not None]
    assert truncated
    assert truncated[0].truncated is not None
    mark = truncated[0].truncated["fields"][0]
    assert mark["field"] == "tool.response.out"
    assert mark["rule"] == "field-size"
    assert mark["original_bytes"] > 100


def test_limits_are_configurable() -> None:
    from agentwatch.configuration import load_config

    cfg = load_config(paths=[], env={}, cli_overrides={"limits.field_bytes": 123})
    assert cfg.limits.field_bytes == 123
