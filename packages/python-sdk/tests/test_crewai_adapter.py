"""Modeled CrewAI adapter tests (M10 10.6 #84).

Shapes are provisional (modeled) until real CrewAI captures land; see
docs/plans/m10-phases-4-5-plan.md.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from agentwatch.adapters import crewai
from agentwatch.records import Outcome, SecurityEventType, StepType, validate_record


def _msg(phase: str, event: dict[str, Any]) -> dict[str, Any]:
    return {"phase": phase, "harness": "crewai", "event": event}


def test_declares_crewai_identity_and_gaps() -> None:
    assert crewai.HARNESS_ID == "crewai"
    assert "tool_usage" in crewai.CAPABILITIES
    assert set(crewai.DOCUMENTED_GAPS).isdisjoint(crewai.CAPABILITIES)


def test_agent_start_is_an_act_record() -> None:
    (record,) = crewai.normalize(
        _msg("agent_start", {"session_id": "s1", "call_id": "c1", "agent": "researcher"})
    )

    assert record.step_type is StepType.ACT
    assert record.agent.identity == "researcher"
    assert record.tool.name == "Agent"
    assert record.ended_at is None
    validate_record(record.to_dict())


def test_task_end_records_error_outcome_and_duration() -> None:
    (record,) = crewai.normalize(
        _msg(
            "task_end",
            {
                "session_id": "s1",
                "call_id": "c2",
                "tool": "ResearchTask",
                "timestamp": "2026-01-02T03:04:07+00:00",
                "duration_ms": 20.0,
                "error": "boom",
            },
        )
    )

    assert record.step_type is StepType.OBSERVE
    assert record.outcome is Outcome.ERROR
    assert record.tool.name == "ResearchTask"
    assert record.ended_at is not None
    assert record.duration_ms == 20.0
    validate_record(record.to_dict())


def test_unknown_phase_is_rejected() -> None:
    with pytest.raises(crewai.CrewAiAdapterError):
        crewai.normalize(_msg("sideways", {"session_id": "s1"}))


@pytest.mark.parametrize("gap", crewai.DOCUMENTED_GAPS)
def test_declared_gaps_are_rejected_explicitly(gap: str) -> None:
    with pytest.raises(crewai.CrewAiAdapterError):
        crewai.normalize({"phase": gap, "event": {"session_id": "s1"}})


def test_secret_in_event_fires_secret_detected() -> None:
    (record,) = crewai.normalize(
        _msg(
            "tool_usage",
            {"session_id": "s1", "call_id": "c", "output": "export TOKEN=sk-abcdefgh"},
        )
    )

    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.SECRET_DETECTED
    assert "sk-abcdefgh" not in str(record.to_dict())


def test_normalize_does_not_mutate_input() -> None:
    message = _msg("agent_start", {"session_id": "s1", "call_id": "c"})
    before = copy.deepcopy(message)
    crewai.normalize(message)
    assert message == before
