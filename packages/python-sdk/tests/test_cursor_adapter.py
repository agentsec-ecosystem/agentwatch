"""Modeled Cursor adapter tests (M10 #80).

Shapes are provisional (modeled) until real Cursor captures land; see
docs/plans/harness-adapters-plan.md.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from agentwatch.adapters import cursor
from agentwatch.records import Outcome, SecurityEventType, StepType, validate_record


def _msg(phase: str, event: dict[str, Any]) -> dict[str, Any]:
    return {"phase": phase, "harness": "cursor", "event": event}


def test_declares_cursor_identity_and_gaps() -> None:
    assert cursor.HARNESS_ID == "cursor"
    assert "beforeShellExecution" in cursor.CAPABILITIES
    assert "afterFileEdit" in cursor.CAPABILITIES
    assert cursor.DOCUMENTED_GAPS == ("mcp-server-events",)


def test_before_shell_is_an_act_record() -> None:
    (record,) = cursor.normalize(
        _msg("beforeShellExecution", {"session_id": "s1", "call_id": "c1", "command": "npm test"})
    )

    assert record.step_type is StepType.ACT
    assert record.tool.name == "Shell"
    assert record.ended_at is None
    assert record.harness == "cursor"
    validate_record(record.to_dict())


def test_after_edit_records_outcome_end_and_duration() -> None:
    (record,) = cursor.normalize(
        _msg(
            "afterFileEdit",
            {
                "session_id": "s1",
                "call_id": "c2",
                "file": "a.py",
                "timestamp": "2026-01-02T03:04:06+00:00",
                "duration_ms": 12.5,
                "error": "boom",
            },
        )
    )

    assert record.step_type is StepType.OBSERVE
    assert record.outcome is Outcome.ERROR
    assert record.tool.name == "Edit"
    assert record.ended_at is not None
    assert record.duration_ms == 12.5
    validate_record(record.to_dict())


def test_unknown_phase_is_rejected() -> None:
    with pytest.raises(cursor.CursorAdapterError):
        cursor.normalize(_msg("sideways", {"session_id": "s1"}))


def test_missing_event_is_rejected() -> None:
    with pytest.raises(cursor.CursorAdapterError):
        cursor.normalize({"phase": "beforeShellExecution"})


def test_secret_in_event_fires_secret_detected() -> None:
    (record,) = cursor.normalize(
        _msg(
            "beforeShellExecution",
            {"session_id": "s1", "call_id": "c", "command": "export TOKEN=sk-abcdefgh"},
        )
    )

    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.SECRET_DETECTED
    assert "sk-abcdefgh" not in json.dumps(record.to_dict())


def test_normalize_does_not_mutate_input() -> None:
    message = _msg("beforeFileEdit", {"session_id": "s1", "call_id": "c", "file": "a.py"})
    before = copy.deepcopy(message)

    cursor.normalize(message)

    assert message == before
