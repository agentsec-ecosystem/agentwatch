"""Proxy framing, pairing, and session-helper tests (M10 N1 #83)."""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from agentwatch import hook, mcp_proxy


def _capture(sent: list[dict[str, Any]]) -> Callable[..., bool]:
    """A typed replacement for ``hook.send`` that records frames."""

    def _send(message: dict[str, Any], **_: Any) -> bool:
        sent.append(message)
        return True

    return _send


def test_resolve_session_id_prefers_agentwatch_then_claude() -> None:
    env = {"AGENTWATCH_SESSION_ID": "a", "CLAUDE_SESSION_ID": "b"}
    assert mcp_proxy.resolve_session_id(env) == "a"
    assert mcp_proxy.resolve_session_id({"CLAUDE_SESSION_ID": "b"}) == "b"
    assert mcp_proxy.resolve_session_id({}).startswith("mcp-")


def test_request_frame_shape() -> None:
    rpc = {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "x"}}
    frame = mcp_proxy.request_frame("github", "s-1", rpc)
    assert frame == {
        "phase": "mcp",
        "harness": "mcp-proxy",
        "event": {
            "server": "github",
            "session_id": "s-1",
            "direction": "request",
            "rpc": {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "x"}},
        },
    }


def test_response_frame_carries_tool_name() -> None:
    frame = mcp_proxy.response_frame(
        "github", "s-1", {"jsonrpc": "2.0", "id": 7, "result": {}}, tool_name="issue_get"
    )
    assert frame["event"]["direction"] == "response"
    assert frame["event"]["tool_name"] == "issue_get"


def test_is_tools_call_request() -> None:
    assert mcp_proxy.is_tools_call_request(
        {"method": "tools/call", "id": 1, "params": {"name": "x"}}
    )
    assert not mcp_proxy.is_tools_call_request({"method": "initialize", "id": 1})
    assert not mcp_proxy.is_tools_call_request([{"method": "tools/call"}])  # batch: not a dict
    assert not mcp_proxy.is_tools_call_request({"method": "tools/call", "params": {}})


def test_recorder_pairs_request_and_response(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(sent))
    recorder = mcp_proxy.Recorder("github", "s-1")

    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "issue_get"}}
    )
    recorder.observe_from_server({"jsonrpc": "2.0", "id": 7, "result": {"ok": True}})

    assert [f["event"]["direction"] for f in sent] == ["request", "response"]
    assert sent[1]["event"]["tool_name"] == "issue_get"


def test_recorder_ignores_an_unpaired_response(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(sent))
    recorder = mcp_proxy.Recorder("github", "s-1")

    recorder.observe_from_server({"jsonrpc": "2.0", "id": 99, "result": {}})

    assert sent == []


def test_flush_pending_records_an_error_for_an_unanswered_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(sent))
    recorder = mcp_proxy.Recorder("github", "s-1")
    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "issue_get"}}
    )

    recorder.flush_pending("server exited")

    assert sent[-1]["event"]["direction"] == "response"
    assert sent[-1]["event"]["tool_name"] == "issue_get"
    assert sent[-1]["event"]["rpc"]["error"]["message"] == "server exited"


def test_request_frame_includes_timestamp_and_cwd() -> None:
    rpc = {"id": 1, "method": "tools/call", "params": {"name": "x"}}
    frame = mcp_proxy.request_frame(
        "github", "s-1", rpc, timestamp="2026-01-02T03:04:05+00:00", cwd="/repo"
    )
    assert frame["event"]["timestamp"] == "2026-01-02T03:04:05+00:00"
    assert frame["event"]["cwd"] == "/repo"


def test_is_tools_call_request_rejects_missing_params() -> None:
    assert not mcp_proxy.is_tools_call_request({"method": "tools/call", "id": 1})


def test_emit_spools_when_daemon_is_down(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(hook, "send", lambda *_args, **_kwargs: False)
    recorder = mcp_proxy.Recorder("github", "s-1", socket_path=str(tmp_path / "d.sock"))

    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "x"}}
    )

    spool = Path(str(tmp_path / "d.sock") + ".spool")
    assert spool.exists()
    assert "mcp" in spool.read_text(encoding="utf-8")


def test_pump_harness_stops_when_the_child_pipe_is_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(sent))
    recorder = mcp_proxy.Recorder("github", "s-1")

    class _ClosedPipe:
        def write(self, data: bytes) -> int:
            raise BrokenPipeError

        def flush(self) -> None:
            raise BrokenPipeError

        def close(self) -> None:
            pass

    payload = b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"x"}}\n'
    pipe = _ClosedPipe()
    mcp_proxy._pump_harness(io.BytesIO(payload), pipe, recorder)  # type: ignore[arg-type]

    assert [f["event"]["direction"] for f in sent] == ["request"]


def test_main_without_command_returns_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert mcp_proxy.main(["--server", "echo"]) == 2
    assert "requires" in capsys.readouterr().err


def test_main_delegates_to_run_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_stdio(server: str, command: list[str], **_: object) -> int:
        captured["server"] = server
        captured["command"] = list(command)
        return 0

    monkeypatch.setattr(mcp_proxy, "run_stdio", fake_run_stdio)
    assert mcp_proxy.main(["--server", "echo", "--", "cmd", "arg"]) == 0
    assert captured == {"server": "echo", "command": ["cmd", "arg"]}


def test_recorder_assigns_a_unique_call_id_per_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(sent))
    recorder = mcp_proxy.Recorder("github", "s-1")
    request = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {"name": "issue_get"},
    }
    response = {"jsonrpc": "2.0", "id": 7, "result": {}}

    recorder.observe_from_harness(request)
    recorder.observe_from_server(response)
    recorder.observe_from_harness(request)
    recorder.observe_from_server(response)

    call_ids = [f["event"]["call_id"] for f in sent]
    assert call_ids[0] == call_ids[1]  # a request and its response share one id
    assert call_ids[2] == call_ids[3]
    assert call_ids[0] != call_ids[2]  # a reused JSON-RPC id gets a fresh call id
