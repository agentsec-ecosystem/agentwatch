"""MCP prompt recording tests (M27 MCP-3 #335).

``prompts/get`` is the second previously-relayed surface the proxy now records.
Like a resource read, the prompt name is **metadata** in
``tool.arguments['name']`` (never the prompt body unless capture is enabled), so
a prompt fetch is provable from the local store alone.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from agentwatch import hook, mcp_proxy
from agentwatch.adapters import mcp_proxy as adapter
from agentwatch.records import StepType

PROMPT = "summarize"


def _frame(**event_overrides: Any) -> dict[str, Any]:
    event: dict[str, Any] = {
        "server": "github",
        "session_id": "s-1",
        "direction": "request",
        "rpc": {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "prompts/get",
            "params": {"name": PROMPT, "arguments": {"style": "terse"}},
        },
        "timestamp": "2026-01-02T03:04:05+00:00",
        "cwd": "/repo",
    }
    event.update(event_overrides)
    return {"phase": "mcp", "harness": "mcp-proxy", "event": event}


def _capture(sent: list[dict[str, Any]]) -> Callable[..., bool]:
    def _send(message: dict[str, Any], **_: Any) -> bool:
        sent.append(message)
        return True

    return _send


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


def test_prompts_get_request_is_recorded() -> None:
    record = adapter.normalize(_frame())[0]
    assert record.tool.name == "prompts/get"
    assert record.tool.server == "github"
    assert record.tool.arguments == {"name": PROMPT}
    assert record.step_type is StepType.ACT
    assert record.span_id == "mcp:github:11"


def test_prompts_get_response_is_recorded() -> None:
    message = _frame(
        direction="response",
        tool_name="prompts/get",
        prompt=PROMPT,
        rpc={"jsonrpc": "2.0", "id": 11, "result": {"messages": []}},
        timestamp="2026-01-02T03:04:06+00:00",
    )
    record = adapter.normalize(message)[0]
    assert record.tool.name == "prompts/get"
    assert record.tool.arguments == {"name": PROMPT}
    assert record.step_type is StepType.OBSERVE
    assert record.ended_at is not None


def test_prompts_get_error_is_an_error_outcome() -> None:
    message = _frame(
        direction="response",
        tool_name="prompts/get",
        prompt=PROMPT,
        rpc={"jsonrpc": "2.0", "id": 11, "error": {"code": -32602, "message": "unknown prompt"}},
    )
    assert adapter.normalize(message)[0].outcome.value == "error"


def test_prompts_get_without_a_name_is_rejected() -> None:
    message = _frame(rpc={"jsonrpc": "2.0", "id": 11, "method": "prompts/get", "params": {}})
    with pytest.raises(adapter.McpProxyAdapterError):
        adapter.normalize(message)


def test_prompts_is_a_capability_not_a_gap() -> None:
    assert "mcp-prompts" in adapter.CAPABILITIES
    assert "mcp-prompts" not in adapter.DOCUMENTED_GAPS
    assert "mcp-sampling" in adapter.DOCUMENTED_GAPS


# ---------------------------------------------------------------------------
# Proxy recorder
# ---------------------------------------------------------------------------


def test_is_prompts_get_request() -> None:
    assert mcp_proxy.is_prompts_get_request(
        {"method": "prompts/get", "id": 1, "params": {"name": PROMPT}}
    )
    assert not mcp_proxy.is_prompts_get_request({"method": "prompts/get", "params": {}})
    assert not mcp_proxy.is_prompts_get_request({"method": "prompts/list"})


def test_recorder_frames_a_prompts_get_request(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(sent))
    recorder = mcp_proxy.Recorder("github", "s-1")

    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 11, "method": "prompts/get", "params": {"name": PROMPT}}
    )

    assert len(sent) == 1
    event = sent[0]["event"]
    assert event["direction"] == "request"
    assert event["tool_name"] == "prompts/get"
    assert event["prompt"] == PROMPT


def test_recorder_pairs_a_prompts_get_response(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(sent))
    recorder = mcp_proxy.Recorder("github", "s-1")

    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 11, "method": "prompts/get", "params": {"name": PROMPT}}
    )
    recorder.observe_from_server({"jsonrpc": "2.0", "id": 11, "result": {"messages": []}})

    response = sent[1]["event"]
    assert response["direction"] == "response"
    assert response["tool_name"] == "prompts/get"
    assert response["prompt"] == PROMPT
