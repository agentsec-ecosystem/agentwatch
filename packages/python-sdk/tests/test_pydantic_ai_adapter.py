"""Modeled PydanticAI record-adapter tests (M10 10.6 #84).

Shapes are provisional (modeled) until real PydanticAI captures land; see
docs/plans/m10-phases-4-5-plan.md. The in-process instrumentation wrapper lives
in ``agentwatch.pydantic`` (covered by ``test_pydantic.py``).
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from agentwatch.adapters import pydantic_ai
from agentwatch.records import Outcome, SecurityEventType, StepType, validate_record


def _msg(phase: str, event: dict[str, Any]) -> dict[str, Any]:
    return {"phase": phase, "harness": "pydantic-ai", "event": event}


def test_declares_pydantic_ai_identity_and_gaps() -> None:
    assert pydantic_ai.HARNESS_ID == "pydantic-ai"
    assert "tool_call" in pydantic_ai.CAPABILITIES
    assert set(pydantic_ai.DOCUMENTED_GAPS).isdisjoint(pydantic_ai.CAPABILITIES)


def test_tool_call_is_an_act_record() -> None:
    (record,) = pydantic_ai.normalize(
        _msg("tool_call", {"session_id": "s1", "call_id": "c1", "tool_name": "get_weather"})
    )

    assert record.step_type is StepType.ACT
    assert record.tool.name == "get_weather"
    assert record.ended_at is None
    validate_record(record.to_dict())


def test_tool_result_is_error_when_is_error() -> None:
    (record,) = pydantic_ai.normalize(
        _msg(
            "tool_result",
            {
                "session_id": "s1",
                "call_id": "c2",
                "tool_name": "get_weather",
                "is_error": True,
                "timestamp": "2026-01-02T03:04:06+00:00",
                "duration_ms": 12.5,
            },
        )
    )

    assert record.step_type is StepType.OBSERVE
    assert record.outcome is Outcome.ERROR
    assert record.ended_at is not None
    validate_record(record.to_dict())


def test_unknown_phase_is_rejected() -> None:
    with pytest.raises(pydantic_ai.PydanticAiAdapterError):
        pydantic_ai.normalize(_msg("sideways", {"session_id": "s1"}))


@pytest.mark.parametrize("gap", pydantic_ai.DOCUMENTED_GAPS)
def test_declared_gaps_are_rejected_explicitly(gap: str) -> None:
    with pytest.raises(pydantic_ai.PydanticAiAdapterError):
        pydantic_ai.normalize({"phase": gap, "event": {"session_id": "s1"}})


def test_secret_in_event_fires_secret_detected() -> None:
    (record,) = pydantic_ai.normalize(
        _msg(
            "tool_call",
            {"session_id": "s1", "call_id": "c", "arguments": "export TOKEN=sk-abcdefgh"},
        )
    )

    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.SECRET_DETECTED
    assert "sk-abcdefgh" not in str(record.to_dict())


def test_normalize_does_not_mutate_input() -> None:
    message = _msg("agent_run_start", {"session_id": "s1", "call_id": "c"})
    before = copy.deepcopy(message)
    pydantic_ai.normalize(message)
    assert message == before
