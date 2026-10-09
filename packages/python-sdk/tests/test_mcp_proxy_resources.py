"""MCP resource recording tests (M27 MCP-2 #334).

The proxy records the previously-relayed ``resources/read`` surface and the
resource links a tool result carries. The resource URI is **metadata** (never
secret content): it rides in ``tool.arguments['uri']`` with metadata-only
privacy, exactly like the ``mcp-surface`` carrier, so ``search --mcp-resource``
can find it without capturing the resource body.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from agentwatch import hook, mcp_proxy
from agentwatch.adapters import mcp_proxy as adapter
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

README = "file:///repo/README.md"


def _frame(**event_overrides: Any) -> dict[str, Any]:
    event: dict[str, Any] = {
        "server": "github",
        "session_id": "s-1",
        "direction": "request",
        "rpc": {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "resources/read",
            "params": {"uri": README},
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


def test_resources_read_request_is_recorded() -> None:
    record = adapter.normalize(_frame())[0]
    assert record.tool.name == "resources/read"
    assert record.tool.server == "github"
    assert record.tool.arguments == {"uri": README}
    assert record.step_type is StepType.ACT
    assert record.span_id == "mcp:github:7"


def test_resources_read_response_is_recorded() -> None:
    message = _frame(
        direction="response",
        tool_name="resources/read",
        resource=README,
        rpc={"jsonrpc": "2.0", "id": 7, "result": {"contents": []}},
        timestamp="2026-01-02T03:04:06+00:00",
    )
    record = adapter.normalize(message)[0]
    assert record.tool.name == "resources/read"
    assert record.tool.arguments == {"uri": README}
    assert record.step_type is StepType.OBSERVE
    assert record.ended_at is not None


def test_resource_link_in_a_tool_result_is_recorded() -> None:
    message = _frame(
        direction="response",
        tool_name="resources/link",
        resource="file:///repo/src/app.py",
        rpc={"jsonrpc": "2.0", "id": 9, "result": {"ok": True}},
    )
    record = adapter.normalize(message)[0]
    assert record.tool.name == "resources/link"
    assert record.tool.arguments == {"uri": "file:///repo/src/app.py"}


def test_resources_read_error_is_an_error_outcome() -> None:
    message = _frame(
        direction="response",
        tool_name="resources/read",
        resource=README,
        rpc={"jsonrpc": "2.0", "id": 7, "error": {"code": -32002, "message": "gone"}},
    )
    assert adapter.normalize(message)[0].outcome is Outcome.ERROR


def test_resources_read_without_uri_is_rejected() -> None:
    message = _frame(rpc={"jsonrpc": "2.0", "id": 7, "method": "resources/read", "params": {}})
    with pytest.raises(adapter.McpProxyAdapterError):
        adapter.normalize(message)


def test_prompts_get_is_still_a_declared_gap() -> None:
    message = _frame(rpc={"jsonrpc": "2.0", "id": 1, "method": "prompts/get", "params": {}})
    with pytest.raises(adapter.McpProxyAdapterError):
        adapter.normalize(message)


def test_resources_is_a_capability_not_a_gap() -> None:
    assert "mcp-resources" in adapter.CAPABILITIES
    assert "mcp-resources" not in adapter.DOCUMENTED_GAPS


# ---------------------------------------------------------------------------
# Proxy recorder
# ---------------------------------------------------------------------------


def test_recorder_frames_a_resources_read_request(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(sent))
    recorder = mcp_proxy.Recorder("github", "s-1")

    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 7, "method": "resources/read", "params": {"uri": README}}
    )

    assert len(sent) == 1
    event = sent[0]["event"]
    assert event["direction"] == "request"
    assert event["tool_name"] == "resources/read"
    assert event["resource"] == README


def test_recorder_pairs_a_resources_read_response(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(sent))
    recorder = mcp_proxy.Recorder("github", "s-1")

    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 7, "method": "resources/read", "params": {"uri": README}}
    )
    recorder.observe_from_server({"jsonrpc": "2.0", "id": 7, "result": {"contents": []}})

    response = sent[1]["event"]
    assert response["direction"] == "response"
    assert response["tool_name"] == "resources/read"
    assert response["resource"] == README


def test_recorder_frames_resource_links_in_a_tool_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(sent))
    recorder = mcp_proxy.Recorder("github", "s-1")

    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "search"}}
    )
    recorder.observe_from_server(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {"type": "text", "text": "hi"},
                    {"type": "resource_link", "uri": "file:///repo/src/app.py", "name": "app"},
                ]
            },
        }
    )

    link_frames = [f["event"] for f in sent if f["event"].get("tool_name") == "resources/link"]
    assert len(link_frames) == 1
    assert link_frames[0]["resource"] == "file:///repo/src/app.py"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def _record(uri: str) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="unknown"),
        tool=ToolCall(name="resources/read", server="github", arguments={"uri": uri}),
        outcome=Outcome.OK,
        started_at=AT,
    )


def test_search_filters_by_mcp_resource(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record(README))
    store.append(
        AgentRecord(
            session_id="s1",
            agent=AgentIdentity(identity="unknown"),
            tool=ToolCall(name="Bash"),
            outcome=Outcome.OK,
            started_at=AT,
        )
    )

    from agentwatch.query import search

    assert [r.tool.name for r in search(store, mcp_resource="README")] == ["resources/read"]
    assert search(store, mcp_resource="not-present") == []


def test_cli_search_mcp_resource(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    store.append(_record(README))

    from agentwatch.cli.main import main

    rc = main(
        ["--set", f"store.path={store_dir}", "search", "--mcp-resource", "README", "--json"]
    )

    assert rc == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["tool"]["arguments"]["uri"] == README
