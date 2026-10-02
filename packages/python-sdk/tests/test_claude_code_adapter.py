"""Tests for the Claude Code adapter (M3 #27).

PreToolUse -> intent record, PostToolUse -> outcome record; both validate against
the M2 record contract. Redaction is applied before a record is produced.
"""

from __future__ import annotations

from typing import Any

import pytest

from agentwatch.adapters import claude_code
from agentwatch.records import Outcome, RecordPrivacyMode, StepType, validate_record
from agentwatch.redact import PrivacyMode, RedactionConfig

PRE: dict[str, Any] = {
    "phase": "pre",
    "harness": "claude-code",
    "event": {
        "session_id": "sess-1",
        "tool_name": "Bash",
        "tool_input": {"cmd": "ls"},
        "tool_use_id": "call-1",
        "timestamp": "2026-01-02T03:04:05+00:00",
        "agent": "triage",
    },
}


def _post(**event_overrides: Any) -> dict[str, Any]:
    event = {
        "session_id": "sess-1",
        "tool_name": "Bash",
        "tool_input": {"cmd": "ls"},
        "tool_use_id": "call-1",
        "timestamp": "2026-01-02T03:04:05.120000+00:00",
        "agent": "triage",
        "duration_ms": 12.5,
        "tool_response": {"ok": True},
    }
    event.update(event_overrides)
    return {"phase": "post", "harness": "claude-code", "event": event}


def test_capabilities_and_gaps_are_declared() -> None:
    assert claude_code.HARNESS_ID == "claude-code"
    assert "pre-tool-use" in claude_code.CAPABILITIES
    assert "post-tool-use" in claude_code.CAPABILITIES
    assert "post-tool-use-failure" in claude_code.CAPABILITIES
    assert "session-boundaries" in claude_code.DOCUMENTED_GAPS


def test_pre_event_produces_an_intent_record() -> None:
    (record,) = claude_code.normalize(PRE)

    assert record.harness == "claude-code"
    assert record.session_id == "sess-1"
    assert record.tool.name == "Bash"
    assert record.step_type is StepType.ACT
    assert record.ended_at is None
    assert record.agent.identity == "triage"
    validate_record(record.to_dict())


def test_post_event_produces_an_outcome_record() -> None:
    (record,) = claude_code.normalize(_post())

    assert record.outcome is Outcome.OK
    assert record.step_type is StepType.OBSERVE
    assert record.ended_at is not None
    assert record.duration_ms == 12.5
    validate_record(record.to_dict())


def test_post_error_response_sets_outcome_error() -> None:
    (record,) = claude_code.normalize(_post(tool_response={"is_error": True, "error": "boom"}))
    assert record.outcome is Outcome.ERROR


def test_pre_and_post_share_a_span_id_for_the_same_tool_call() -> None:
    (pre,) = claude_code.normalize(PRE)
    (post,) = claude_code.normalize(_post())

    assert pre.span_id is not None
    assert pre.span_id == post.span_id


def test_different_tool_calls_get_different_span_ids() -> None:
    (first,) = claude_code.normalize(PRE)
    (second,) = claude_code.normalize(_post(tool_use_id="call-2"))
    assert first.span_id != second.span_id


def test_unknown_phase_is_rejected() -> None:
    with pytest.raises(claude_code.ClaudeCodeAdapterError):
        claude_code.normalize({"phase": "sideways", "event": PRE["event"]})


def test_missing_event_is_rejected() -> None:
    with pytest.raises(claude_code.ClaudeCodeAdapterError):
        claude_code.normalize({"phase": "pre"})


def test_default_metadata_only_omits_arguments() -> None:
    (record,) = claude_code.normalize(PRE)
    assert record.tool.arguments is None
    assert record.tool.privacy_mode is RecordPrivacyMode.METADATA_ONLY


def test_truncated_mode_captures_redacted_arguments() -> None:
    cfg = RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_tool_args=True)
    (record,) = claude_code.normalize(PRE, redaction=cfg)

    assert record.tool.arguments == {"cmd": "ls"}
    assert record.tool.privacy_mode is RecordPrivacyMode.TRUNCATED


def test_hashed_mode_hashes_string_arguments() -> None:
    cfg = RedactionConfig(mode=PrivacyMode.HASHED, capture_tool_args=True, hash_salt="s")
    (record,) = claude_code.normalize(PRE, redaction=cfg)

    assert record.tool.arguments is not None
    assert record.tool.arguments["cmd"] != "ls"
    assert record.tool.privacy_mode is RecordPrivacyMode.HASHED
