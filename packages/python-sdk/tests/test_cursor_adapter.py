"""Cursor native-hooks adapter tests (M25 CUR-2, #304).

Cursor ships ``hooks.json`` that invoke an external program with JSON on stdin
across the full agent loop. The hook binary frames the payload as
``{"phase": <hook_event_name>, "harness": "cursor", "event": {...}}``; this
adapter normalizes that framed message.

Blocking before-events are recorded as observations and are **never answered**
(monitor-only, R2). Cloud-agent hook gaps are declared, never silent.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import conformance_registry
import pytest

from agentwatch import conformance
from agentwatch.adapters import cursor
from agentwatch.records import Outcome, SecurityEventType, StepType, validate_record


def _msg(phase: str, event: dict[str, Any]) -> dict[str, Any]:
    return {"phase": phase, "harness": "cursor", "event": event}


def test_declares_native_capabilities_and_cloud_gaps() -> None:
    assert cursor.HARNESS_ID == "cursor"
    for phase in (
        "sessionStart",
        "sessionEnd",
        "preToolUse",
        "postToolUse",
        "postToolUseFailure",
        "beforeShellExecution",
        "afterShellExecution",
        "beforeMCPExecution",
        "afterMCPExecution",
        "beforeReadFile",
        "afterFileEdit",
        "subagentStart",
        "subagentStop",
        "beforeSubmitPrompt",
        "preCompact",
        "afterAgentThought",
        "afterAgentResponse",
        "beforeTabFileRead",
        "afterTabFileEdit",
        "workspaceOpen",
    ):
        assert phase in cursor.CAPABILITIES
    assert cursor.DOCUMENTED_GAPS == ("cloud-agent-hook-events",)
    assert set(cursor.DOCUMENTED_GAPS).isdisjoint(cursor.CAPABILITIES)


def test_blocking_event_is_recorded_as_an_observation_and_never_answered() -> None:
    (record,) = cursor.normalize(
        _msg(
            "beforeShellExecution",
            {
                "session_id": "s1",
                "call_id": "c1",
                "command": "npm test",
                "permission": "deny",  # a blocking decision we must NOT answer
            },
        )
    )

    assert record.step_type is StepType.ACT
    assert record.tool.name == "Shell"
    assert record.ended_at is None
    assert record.approval is None  # never recorded an authorization we did not make
    assert record.outcome is Outcome.OK
    validate_record(record.to_dict())


def test_after_shell_records_outcome_end_and_duration() -> None:
    (record,) = cursor.normalize(
        _msg(
            "afterShellExecution",
            {
                "session_id": "s1",
                "call_id": "c1",
                "timestamp": "2026-01-02T03:04:06+00:00",
                "duration_ms": 12.5,
                "error": "boom",
            },
        )
    )

    assert record.step_type is StepType.OBSERVE
    assert record.outcome is Outcome.ERROR
    assert record.tool.name == "Shell"
    assert record.ended_at is not None
    assert record.duration_ms == 12.5
    validate_record(record.to_dict())


def test_pre_and_post_tool_use_share_the_tool_name() -> None:
    (pre,) = cursor.normalize(
        _msg("preToolUse", {"session_id": "s1", "call_id": "c1", "tool_name": "Read"})
    )
    (post,) = cursor.normalize(
        _msg("postToolUse", {"session_id": "s1", "call_id": "c1", "tool_name": "Read"})
    )

    assert pre.tool.name == "Read" and pre.step_type is StepType.ACT
    assert post.tool.name == "Read" and post.step_type is StepType.OBSERVE
    assert post.ended_at is not None
    assert post.span_id == pre.span_id == "c1"


def test_post_tool_use_failure_is_an_error() -> None:
    (record,) = cursor.normalize(
        _msg("postToolUseFailure", {"session_id": "s1", "call_id": "c1", "tool_name": "Bash"})
    )

    assert record.outcome is Outcome.ERROR
    assert record.tool.name == "Bash"


def test_mcp_execution_records_server_attribution() -> None:
    (record,) = cursor.normalize(
        _msg(
            "beforeMCPExecution",
            {"session_id": "s1", "call_id": "c1", "tool_name": "mcp__github__issue_get"},
        )
    )

    assert record.tool.name == "issue_get"
    assert record.tool.server == "github"
    assert record.step_type is StepType.ACT


def test_before_read_file_is_an_observe_step() -> None:
    (record,) = cursor.normalize(
        _msg("beforeReadFile", {"session_id": "s1", "call_id": "c1", "file": "a.py"})
    )

    assert record.step_type is StepType.OBSERVE
    assert record.tool.name == "Read"


def test_subagent_start_sets_the_subagent_identity() -> None:
    (record,) = cursor.normalize(
        _msg(
            "subagentStart",
            {"session_id": "s1", "call_id": "c1", "agent_id": "sub-7", "agent_type": "explore"},
        )
    )

    assert record.agent.identity == "sub-7"
    assert record.agent.name == "explore"
    assert record.tool.name == "subagent"


def test_before_submit_prompt_is_a_reason_step() -> None:
    (record,) = cursor.normalize(
        _msg("beforeSubmitPrompt", {"session_id": "s1", "prompt": "hello"})
    )

    assert record.step_type is StepType.REASON
    assert record.tool.name == "user-prompt"
    # Metadata-only by default: the prompt is never stored.
    assert record.tool.arguments is None


def test_after_agent_thought_is_reasoning_and_metadata_only() -> None:
    (record,) = cursor.normalize(
        _msg("afterAgentThought", {"session_id": "s1", "thought": "let me think"})
    )

    assert record.step_type is StepType.REASON
    assert record.tool.name == "agent-thought"
    assert record.tool.arguments is None


def test_pre_compact_records_only_the_trigger() -> None:
    (record,) = cursor.normalize(
        _msg(
            "preCompact",
            {"session_id": "s1", "trigger": "auto", "tokens_before": 1000},
        )
    )

    assert record.tool.name == "context-compacted"
    assert record.tool.arguments == {"trigger": "auto", "tokens_before": 1000}


def test_tab_hooks_are_tagged() -> None:
    (read,) = cursor.normalize(
        _msg("beforeTabFileRead", {"session_id": "s1", "call_id": "c1", "file": "a.py"})
    )
    (edit,) = cursor.normalize(
        _msg("afterTabFileEdit", {"session_id": "s1", "call_id": "c2", "file": "a.py"})
    )

    assert read.tool.name == "TabRead" and read.step_type is StepType.OBSERVE
    assert edit.tool.name == "TabEdit" and edit.ended_at is not None


def test_workspace_open_is_a_lifecycle_record() -> None:
    (record,) = cursor.normalize(_msg("workspaceOpen", {"session_id": "s1"}))

    assert record.tool.name == "workspace-open"
    assert record.step_type is None


def test_session_boundaries_are_lifecycle_records() -> None:
    (start,) = cursor.normalize(
        _msg("sessionStart", {"session_id": "s1", "ide": "cursor-remote"})
    )
    (end,) = cursor.normalize(
        _msg("sessionEnd", {"session_id": "s1", "reason": "fork", "parent_session_id": "p0"})
    )

    assert start.step_type is None and start.tool.name == "session-start"
    assert end.step_type is None and end.tool.name == "session-end"
    assert end.parent_session_id == "p0"


def test_ide_is_tagged_on_every_record() -> None:
    for phase, event in (
        ("beforeShellExecution", {"session_id": "s1", "command": "ls"}),
        ("sessionStart", {"session_id": "s1"}),
        ("afterAgentThought", {"session_id": "s1"}),
    ):
        (record,) = cursor.normalize(_msg(phase, {**event, "ide": "cursor-cli"}))
        assert record.environment == {"ide": "cursor-cli"}


def test_unknown_phase_is_rejected() -> None:
    with pytest.raises(cursor.CursorAdapterError):
        cursor.normalize(_msg("sideways", {"session_id": "s1"}))


@pytest.mark.parametrize("gap", cursor.DOCUMENTED_GAPS)
def test_declared_gap_is_rejected(gap: str) -> None:
    with pytest.raises(cursor.CursorAdapterError):
        cursor.normalize(_msg(gap, {"session_id": "s1"}))


def test_missing_event_is_rejected() -> None:
    with pytest.raises(cursor.CursorAdapterError):
        cursor.normalize({"phase": "beforeShellExecution"})


def test_secret_in_event_fires_secret_detected() -> None:
    (record,) = cursor.normalize(
        _msg(
            "beforeSubmitPrompt",
            {"session_id": "s1", "prompt": "export TOKEN=sk-abcdefgh"},
        )
    )

    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.SECRET_DETECTED
    assert "sk-abcdefgh" not in json.dumps(record.to_dict())


def test_normalize_does_not_mutate_input() -> None:
    message = _msg("beforeReadFile", {"session_id": "s1", "call_id": "c", "file": "a.py"})
    before = copy.deepcopy(message)

    cursor.normalize(message)

    assert message == before


def test_cursor_passes_the_shared_conformance_runner() -> None:
    conformance.assert_conforms(conformance_registry.cursor_spec())
