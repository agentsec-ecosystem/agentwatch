"""MCP elicitation recording tests (M27 MCP-4 #336).

Elicitation is the human-input surface: a server asks the client for input and
the client answers. The proxy records both directions and links the answer to
approval provenance (S14) — ``accept`` → ``user``, ``decline`` → ``denied``,
and an answer that does not expose an action stays honest ``unknown``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from agentwatch import hook, mcp_proxy
from agentwatch.adapters import mcp_proxy as adapter
from agentwatch.records import Approval, StepType


def _request(**overrides: Any) -> dict[str, Any]:
    event: dict[str, Any] = {
        "server": "github",
        "session_id": "s-1",
        "direction": "request",
        "rpc": {
            "jsonrpc": "2.0",
            "id": 21,
            "method": "elicitation/create",
            "params": {"message": "Approve the deploy?"},
        },
        "timestamp": "2026-01-02T03:04:05+00:00",
    }
    event.update(overrides)
    return {"phase": "mcp", "harness": "mcp-proxy", "event": event}


def _response(action: str | None, **overrides: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if action is not None:
        result["action"] = action
    event: dict[str, Any] = {
        "server": "github",
        "session_id": "s-1",
        "direction": "response",
        "tool_name": "elicitation/create",
        "rpc": {"jsonrpc": "2.0", "id": 21, "result": result},
        "timestamp": "2026-01-02T03:04:06+00:00",
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


def test_elicitation_request_is_recorded() -> None:
    record = adapter.normalize(_request())[0]
    assert record.tool.name == "elicitation/create"
    assert record.tool.server == "github"
    assert record.step_type is StepType.ACT
    assert record.span_id == "mcp:github:21"


def test_accept_links_approval_to_user() -> None:
    record = adapter.normalize(_response("accept"))[0]
    assert record.step_type is StepType.OBSERVE
    assert record.approval is Approval.USER


def test_decline_links_approval_to_denied() -> None:
    assert adapter.normalize(_response("decline"))[0].approval is Approval.DENIED


def test_absent_action_is_honest_unknown() -> None:
    assert adapter.normalize(_response(None))[0].approval is Approval.UNKNOWN


def test_unrecognized_action_is_honest_unknown() -> None:
    assert adapter.normalize(_response("maybe"))[0].approval is Approval.UNKNOWN


def test_elicitation_is_a_capability_not_a_gap() -> None:
    assert "mcp-elicitation" in adapter.CAPABILITIES
    assert "mcp-elicitation" not in adapter.DOCUMENTED_GAPS


# ---------------------------------------------------------------------------
# Proxy recorder
# ---------------------------------------------------------------------------


def test_is_elicitation_request() -> None:
    assert mcp_proxy.is_elicitation_request(
        {"method": "elicitation/create", "id": 1, "params": {"message": "?"}}
    )
    assert not mcp_proxy.is_elicitation_request({"method": "tools/call"})


def test_recorder_pairs_a_server_elicitation(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(sent))
    recorder = mcp_proxy.Recorder("github", "s-1")

    recorder.observe_from_server(
        {"jsonrpc": "2.0", "id": 21, "method": "elicitation/create", "params": {"message": "?"}}
    )
    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 21, "result": {"action": "accept"}}
    )

    assert [f["event"]["direction"] for f in sent] == ["request", "response"]
    assert sent[0]["event"]["tool_name"] == "elicitation/create"
    assert sent[0]["event"]["server"] == "github"
    assert sent[1]["event"]["tool_name"] == "elicitation/create"
    assert sent[1]["event"]["rpc"]["result"]["action"] == "accept"
    assert sent[0]["event"]["call_id"] == sent[1]["event"]["call_id"]


def test_flush_records_an_unanswered_elicitation(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(sent))
    recorder = mcp_proxy.Recorder("github", "s-1")

    recorder.observe_from_server(
        {"jsonrpc": "2.0", "id": 21, "method": "elicitation/create", "params": {}}
    )
    recorder.flush_pending("server exited")

    assert sent[-1]["event"]["direction"] == "response"
    assert sent[-1]["event"]["rpc"]["error"]["message"] == "server exited"
