"""MCP tasks lifecycle recording tests (M27 MCP-5 #337).

The 2026-07-28 revision adds durable **tasks** (SEP-2663) and deprecates
Roots/Sampling/Logging (SEP-2577). The proxy records the task lifecycle
(``tasks/get``/``tasks/cancel``/… and a task-augmented tool result) with the task
id as metadata; the retired surfaces are **closed-by-spec**, not our gaps.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from agentwatch import hook, mcp_proxy
from agentwatch.adapters import mcp_proxy as adapter
from agentwatch.records import StepType

TASK = "task-9f2"


def _task_request(method: str = "tasks/get", **overrides: Any) -> dict[str, Any]:
    event: dict[str, Any] = {
        "server": "github",
        "session_id": "s-1",
        "direction": "request",
        "rpc": {"jsonrpc": "2.0", "id": 31, "method": method, "params": {"taskId": TASK}},
        "timestamp": "2026-01-02T03:04:05+00:00",
        "cwd": "/repo",
    }
    event.update(overrides)
    return {"phase": "mcp", "harness": "mcp-proxy", "event": event}


def _capture(sent: list[dict[str, Any]]) -> Callable[..., bool]:
    def _send(message: dict[str, Any], **_: Any) -> bool:
        sent.append(message)
        return True

    return _send


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


def test_tasks_get_request_is_recorded() -> None:
    record = adapter.normalize(_task_request())[0]
    assert record.tool.name == "tasks/get"
    assert record.tool.server == "github"
    assert record.tool.arguments == {"taskId": TASK}
    assert record.step_type is StepType.ACT


def test_tasks_get_response_is_recorded() -> None:
    message = _task_request(
        direction="response",
        tool_name="tasks/get",
        task=TASK,
        rpc={"jsonrpc": "2.0", "id": 31, "result": {"status": "running"}},
        timestamp="2026-01-02T03:04:06+00:00",
    )
    record = adapter.normalize(message)[0]
    assert record.tool.name == "tasks/get"
    assert record.tool.arguments == {"taskId": TASK}
    assert record.step_type is StepType.OBSERVE


def test_tasks_cancel_is_recorded() -> None:
    record = adapter.normalize(_task_request("tasks/cancel"))[0]
    assert record.tool.name == "tasks/cancel"


def test_task_augmented_tool_result_keeps_the_task_id() -> None:
    message = _task_request(
        direction="response",
        tool_name="deploy",
        rpc={"jsonrpc": "2.0", "id": 5, "result": {"task": {"id": TASK, "status": "working"}}},
    )
    record = adapter.normalize(message)[0]
    assert record.tool.name == "deploy"
    assert record.tool.arguments == {"taskId": TASK}


def test_tasks_is_a_capability_and_deprecated_surfaces_are_closed_by_spec() -> None:
    assert "mcp-tasks" in adapter.CAPABILITIES
    assert "mcp-sampling" in adapter.DOCUMENTED_GAPS
    assert "mcp-roots" in adapter.DOCUMENTED_GAPS
    assert "mcp-logging" in adapter.DOCUMENTED_GAPS


# ---------------------------------------------------------------------------
# Proxy recorder
# ---------------------------------------------------------------------------


def test_is_tasks_request() -> None:
    assert mcp_proxy.is_tasks_request({"method": "tasks/get", "id": 1, "params": {"taskId": TASK}})
    assert mcp_proxy.is_tasks_request({"method": "tasks/cancel", "id": 2})
    assert not mcp_proxy.is_tasks_request({"method": "tools/call"})


def test_recorder_pairs_a_tasks_request(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(sent))
    recorder = mcp_proxy.Recorder("github", "s-1")

    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 31, "method": "tasks/get", "params": {"taskId": TASK}}
    )
    recorder.observe_from_server({"jsonrpc": "2.0", "id": 31, "result": {"status": "running"}})

    assert [f["event"]["direction"] for f in sent] == ["request", "response"]
    assert sent[0]["event"]["tool_name"] == "tasks/get"
    assert sent[0]["event"]["task"] == TASK
    assert sent[1]["event"]["task"] == TASK
    assert sent[0]["event"]["call_id"] == sent[1]["event"]["call_id"]


def test_flush_records_an_unanswered_task(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(sent))
    recorder = mcp_proxy.Recorder("github", "s-1")

    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 31, "method": "tasks/get", "params": {"taskId": TASK}}
    )
    recorder.flush_pending("server exited")

    assert sent[-1]["event"]["direction"] == "response"
    assert sent[-1]["event"]["task"] == TASK
