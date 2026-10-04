"""Modeled Gemini CLI adapter tests (M10 #82).

Shapes are provisional (modeled); see docs/plans/harness-adapters-plan.md.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from agentwatch.adapters import gemini_cli
from agentwatch.records import Outcome, SecurityEventType, StepType, validate_record


def _msg(phase: str, event: dict[str, Any]) -> dict[str, Any]:
    return {"phase": phase, "harness": "gemini-cli", "event": event}


def test_declares_identity_and_gaps() -> None:
    assert gemini_cli.HARNESS_ID == "gemini-cli"
    assert "tool_call" in gemini_cli.CAPABILITIES
    assert gemini_cli.DOCUMENTED_GAPS == ("mcp-server-events",)


def test_tool_call_is_an_act_record() -> None:
    (record,) = gemini_cli.normalize(
        _msg("tool_call", {"session_id": "s1", "call_id": "c1", "tool": "search"})
    )

    assert record.step_type is StepType.ACT
    assert record.tool.name == "search"
    assert record.ended_at is None
    validate_record(record.to_dict())


def test_tool_result_error_is_an_observe_record() -> None:
    (record,) = gemini_cli.normalize(
        _msg(
            "tool_result",
            {
                "session_id": "s1",
                "call_id": "c1",
                "tool": "search",
                "timestamp": "2026-01-02T03:04:06+00:00",
                "is_error": True,
                "duration_ms": 3.0,
            },
        )
    )

    assert record.step_type is StepType.OBSERVE
    assert record.outcome is Outcome.ERROR
    assert record.ended_at is not None
    assert record.duration_ms == 3.0
    validate_record(record.to_dict())


def test_session_start_is_a_boundary_record() -> None:
    (record,) = gemini_cli.normalize(
        _msg("session_start", {"session_id": "s1", "timestamp": "2026-01-02T03:04:00+00:00"})
    )

    assert record.step_type is None
    assert record.tool.name == "session_start"
    assert record.ended_at is None
    validate_record(record.to_dict())


def test_unknown_phase_is_rejected() -> None:
    with pytest.raises(gemini_cli.GeminiCliAdapterError):
        gemini_cli.normalize(_msg("sideways", {"session_id": "s1"}))


def test_secret_fires_secret_detected() -> None:
    (record,) = gemini_cli.normalize(
        _msg(
            "tool_call",
            {"session_id": "s1", "call_id": "c", "tool": "curl", "arg": "sk-abcdefgh"},
        )
    )
    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.SECRET_DETECTED
    assert "sk-abcdefgh" not in json.dumps(record.to_dict())


def test_normalize_does_not_mutate_input() -> None:
    message = _msg("tool_call", {"session_id": "s1", "call_id": "c", "tool": "search"})
    before = copy.deepcopy(message)

    gemini_cli.normalize(message)

    assert message == before
