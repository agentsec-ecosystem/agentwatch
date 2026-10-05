"""Cursor native-hooks adapter tests (M25 CUR-2, #304; realigned to CUR-1 corpus).

Field names follow the published Cursor contract (``conversation_id``,
``generation_id``, ``hook_event_name``, ``cursor_version``, ``workspace_roots``,
``file_path``, ``user_email``). The adapter consumes the framed message
``{"phase": <hook_event_name>, "harness": "cursor", "event": {...}}``.

Blocking permission hooks are recorded as observations and are **never answered**
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


def _msg(phase: str, **event: Any) -> dict[str, Any]:
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
        "beforeTabFileRead",
        "afterTabFileEdit",
        "subagentStart",
        "subagentStop",
        "beforeSubmitPrompt",
        "preCompact",
        "stop",
        "afterAgentResponse",
        "afterAgentThought",
        "workspaceOpen",
    ):
        assert phase in cursor.CAPABILITIES
    assert cursor.DOCUMENTED_GAPS == ("cloud-agent-hook-events",)
    assert set(cursor.DOCUMENTED_GAPS).isdisjoint(cursor.CAPABILITIES)


def test_blocking_hook_is_recorded_as_an_observation_and_never_answered() -> None:
    (record,) = cursor.normalize(
        _msg(
            "beforeShellExecution",
            conversation_id="s1",
            command="npm test",
            permission="deny",  # a blocking decision we must NOT answer
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
            conversation_id="s1",
            command="npm test",
            output="boom",
            duration=12.5,
            timestamp="2026-01-02T03:04:06+00:00",
        )
    )

    assert record.step_type is StepType.OBSERVE
    assert record.outcome is Outcome.OK
    assert record.tool.name == "Shell"
    assert record.ended_at is not None
    assert record.duration_ms == 12.5
    validate_record(record.to_dict())


def test_pre_and_post_tool_use_share_the_tool_name_and_span() -> None:
    (pre,) = cursor.normalize(
        _msg("preToolUse", conversation_id="s1", tool_name="Read", tool_use_id="c1")
    )
    (post,) = cursor.normalize(
        _msg("postToolUse", conversation_id="s1", tool_name="Read", tool_use_id="c1")
    )

    assert pre.tool.name == "Read" and pre.step_type is StepType.ACT
    assert post.tool.name == "Read" and post.step_type is StepType.OBSERVE
    assert post.ended_at is not None
    assert post.span_id == pre.span_id == "c1"


def test_post_tool_use_failure_is_an_error() -> None:
    (record,) = cursor.normalize(
        _msg(
            "postToolUseFailure",
            conversation_id="s1",
            tool_name="Bash",
            tool_use_id="c1",
            failure_type="timeout",
            error_message="Command timed out",
        )
    )

    assert record.outcome is Outcome.ERROR
    assert record.tool.name == "Bash"


def test_mcp_execution_records_server_attribution() -> None:
    (record,) = cursor.normalize(
        _msg(
            "beforeMCPExecution",
            conversation_id="s1",
            tool_name="issue_get",
            mcp_server_name="github",
            tool_input="{}",
        )
    )

    assert record.tool.name == "issue_get"
    assert record.tool.server == "github"
    assert record.step_type is StepType.ACT


def test_before_read_file_is_an_observe_step() -> None:
    (record,) = cursor.normalize(
        _msg("beforeReadFile", conversation_id="s1", tool_use_id="c1", file_path="/repo/a.py")
    )

    assert record.step_type is StepType.OBSERVE
    assert record.tool.name == "Read"
    assert record.project is None


def test_subagent_start_sets_the_subagent_identity() -> None:
    (record,) = cursor.normalize(
        _msg(
            "subagentStart",
            conversation_id="s1",
            subagent_id="sub-7",
            subagent_type="explore",
            task="find the auth flow",
        )
    )

    assert record.agent.identity == "sub-7"
    assert record.agent.name == "explore"
    assert record.tool.name == "subagent"


def test_before_submit_prompt_is_a_reason_step() -> None:
    (record,) = cursor.normalize(_msg("beforeSubmitPrompt", conversation_id="s1", prompt="hello"))

    assert record.step_type is StepType.REASON
    assert record.tool.name == "user-prompt"
    # Metadata-only by default: the prompt is never stored.
    assert record.tool.arguments is None


def test_after_agent_thought_is_reasoning_and_metadata_only() -> None:
    (record,) = cursor.normalize(
        _msg("afterAgentThought", conversation_id="s1", text="let me think", duration_ms=5000)
    )

    assert record.step_type is StepType.REASON
    assert record.tool.name == "agent-thought"
    assert record.tool.arguments is None
    assert record.duration_ms == 5000


def test_pre_compact_records_only_metadata() -> None:
    (record,) = cursor.normalize(
        _msg(
            "preCompact",
            conversation_id="s1",
            trigger="auto",
            context_tokens=1000,
            messages_to_compact=30,
        )
    )

    assert record.tool.name == "context-compacted"
    assert record.tool.arguments == {
        "trigger": "auto",
        "context_tokens": 1000,
        "messages_to_compact": 30,
    }


def test_tab_hooks_are_tagged() -> None:
    (read,) = cursor.normalize(
        _msg("beforeTabFileRead", conversation_id="s1", file_path="/repo/a.py")
    )
    (edit,) = cursor.normalize(
        _msg("afterTabFileEdit", conversation_id="s1", file_path="/repo/a.py", duration=3)
    )

    assert read.tool.name == "TabRead" and read.step_type is StepType.OBSERVE
    assert edit.tool.name == "TabEdit" and edit.ended_at is not None


def test_stop_is_a_lifecycle_record() -> None:
    (completed,) = cursor.normalize(
        _msg("stop", conversation_id="s1", status="completed", loop_count=0)
    )
    (errored,) = cursor.normalize(_msg("stop", conversation_id="s1", status="error"))

    assert completed.tool.name == "agent-stop"
    assert completed.step_type is None
    assert completed.outcome is Outcome.OK
    assert errored.outcome is Outcome.ERROR


def test_workspace_open_is_a_lifecycle_record() -> None:
    (record,) = cursor.normalize(
        _msg("workspaceOpen", workspace_roots=["/repo"], cursor_version="1.7.2")
    )

    assert record.tool.name == "workspace-open"
    assert record.step_type is None
    assert record.project == "/repo"
    assert record.producer is not None and record.producer.version == "1.7.2"


def test_session_start_stores_the_ide_and_hashes_the_principal() -> None:
    (record,) = cursor.normalize(
        _msg(
            "sessionStart",
            session_id="s1",
            ide="cursor-remote",
            user_email="alice@example.com",
            composer_mode="agent",
        )
    )

    assert record.step_type is None and record.tool.name == "session-start"
    assert record.environment == {"ide": "cursor-remote"}
    # IDN-1: the principal is hashed by default, never stored in the clear.
    assert record.agent.principal is not None
    assert record.agent.principal != "alice@example.com"


def test_session_end_carries_reason_and_duration() -> None:
    (record,) = cursor.normalize(
        _msg("sessionEnd", session_id="s1", reason="user_close", duration_ms=45000)
    )

    assert record.step_type is None and record.tool.name == "session-end"
    assert record.duration_ms == 45000
    assert record.tool.arguments == {"reason": "user_close"}


def test_ide_is_tagged_on_every_record() -> None:
    for phase, event in (
        ("beforeShellExecution", {"conversation_id": "s1", "command": "ls"}),
        ("sessionStart", {"session_id": "s1"}),
        ("afterAgentThought", {"conversation_id": "s1", "text": "x"}),
    ):
        (record,) = cursor.normalize(_msg(phase, ide="cursor-cli", **event))
        assert record.environment == {"ide": "cursor-cli"}


def test_unknown_phase_is_rejected() -> None:
    with pytest.raises(cursor.CursorAdapterError):
        cursor.normalize(_msg("sideways", conversation_id="s1"))


@pytest.mark.parametrize("gap", cursor.DOCUMENTED_GAPS)
def test_declared_gap_is_rejected(gap: str) -> None:
    with pytest.raises(cursor.CursorAdapterError):
        cursor.normalize(_msg(gap, conversation_id="s1"))


def test_missing_event_is_rejected() -> None:
    with pytest.raises(cursor.CursorAdapterError):
        cursor.normalize({"phase": "beforeShellExecution"})


def test_secret_in_event_fires_secret_detected() -> None:
    (record,) = cursor.normalize(
        _msg("beforeSubmitPrompt", conversation_id="s1", prompt="export TOKEN=sk-abcdefgh")
    )

    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.SECRET_DETECTED
    assert "sk-abcdefgh" not in json.dumps(record.to_dict())


def test_normalize_does_not_mutate_input() -> None:
    message = _msg("beforeReadFile", conversation_id="s1", file_path="/repo/a.py")
    before = copy.deepcopy(message)

    cursor.normalize(message)

    assert message == before


def test_cursor_passes_the_shared_conformance_runner() -> None:
    conformance.assert_conforms(conformance_registry.cursor_spec())
