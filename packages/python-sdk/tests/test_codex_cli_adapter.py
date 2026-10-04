"""Modeled Codex CLI adapter tests (M10 #81).

Shapes are provisional (modeled); see docs/plans/harness-adapters-plan.md.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from agentwatch.adapters import codex_cli
from agentwatch.records import Outcome, SecurityEventType, StepType, validate_record


def _msg(phase: str, event: dict[str, Any]) -> dict[str, Any]:
    return {"phase": phase, "harness": "codex-cli", "event": event}


def test_declares_identity_and_gaps() -> None:
    assert codex_cli.HARNESS_ID == "codex-cli"
    assert "exec_begin" in codex_cli.CAPABILITIES
    assert codex_cli.DOCUMENTED_GAPS == ("mcp-server-events",)


def test_exec_begin_is_an_act_record() -> None:
    (record,) = codex_cli.normalize(
        _msg("exec_begin", {"session_id": "s1", "call_id": "c1", "command": "pytest"})
    )

    assert record.step_type is StepType.ACT
    assert record.tool.name == "shell"
    assert record.ended_at is None
    validate_record(record.to_dict())


def test_exec_end_with_nonzero_exit_is_an_error_observe_record() -> None:
    (record,) = codex_cli.normalize(
        _msg(
            "exec_end",
            {
                "session_id": "s1",
                "call_id": "c1",
                "timestamp": "2026-01-02T03:04:06+00:00",
                "exit_code": 1,
                "duration_ms": 5.0,
            },
        )
    )

    assert record.step_type is StepType.OBSERVE
    assert record.outcome is Outcome.ERROR
    assert record.ended_at is not None
    assert record.duration_ms == 5.0
    validate_record(record.to_dict())


def test_patch_apply_records_a_successful_act() -> None:
    (record,) = codex_cli.normalize(
        _msg(
            "patch_apply",
            {"session_id": "s1", "call_id": "c2", "patch": "*** Begin Patch", "success": True},
        )
    )

    assert record.step_type is StepType.ACT
    assert record.outcome is Outcome.OK
    assert record.tool.name == "apply_patch"
    assert record.ended_at is not None


def test_patch_apply_failure_is_an_error() -> None:
    (record,) = codex_cli.normalize(
        _msg("patch_apply", {"session_id": "s1", "call_id": "c2", "success": False})
    )
    assert record.outcome is Outcome.ERROR


def test_unknown_phase_is_rejected() -> None:
    with pytest.raises(codex_cli.CodexCliAdapterError):
        codex_cli.normalize(_msg("nope", {"session_id": "s1"}))


def test_secret_fires_secret_detected() -> None:
    (record,) = codex_cli.normalize(
        _msg("exec_begin", {"session_id": "s1", "call_id": "c", "command": "export K=sk-abcdefgh"})
    )
    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.SECRET_DETECTED
    assert "sk-abcdefgh" not in json.dumps(record.to_dict())


def test_normalize_does_not_mutate_input() -> None:
    message = _msg("exec_begin", {"session_id": "s1", "call_id": "c", "command": "ls"})
    before = copy.deepcopy(message)

    codex_cli.normalize(message)

    assert message == before
