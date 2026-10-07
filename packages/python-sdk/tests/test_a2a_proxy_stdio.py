"""stdio relay tests for the A2A proxy (M29 A2A-1 #364)."""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from agentwatch import a2a_proxy, hook

ECHO = Path(__file__).resolve().parent / "fixtures" / "a2a" / "echo_agent.py"


def _capture(sent: list[dict[str, Any]]) -> Callable[..., bool]:
    def _send(message: dict[str, Any], **_: Any) -> bool:
        sent.append(message)
        return True

    return _send


def _run(
    payload: bytes,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    frames: list[dict[str, Any]],
) -> bytes:
    monkeypatch.setattr(hook, "send", _capture(frames))
    stdin, stdout = io.BytesIO(payload), io.BytesIO()
    a2a_proxy.run_stdio(
        "echo",
        [sys.executable, str(ECHO)],
        socket_path=str(tmp_path / "d.sock"),
        stdin=stdin,
        stdout=stdout,
        env={},
    )
    return stdout.getvalue()


def test_records_request_and_response(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    frames: list[dict[str, Any]] = []
    request = (
        b'{"jsonrpc":"2.0","id":7,"method":"message/send",'
        b'"params":{"message":{"messageId":"m-1","taskId":"t-1"}}}\n'
    )
    out = _run(request, monkeypatch, tmp_path, frames)

    assert json.loads(out)["result"]["kind"] == "task"
    assert [f["event"]["direction"] for f in frames] == ["request", "response"]
    assert frames[0]["phase"] == "a2a"
    assert frames[1]["event"]["tool_name"] == "message/send"


def test_forwards_non_recordable_lines_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frames: list[dict[str, Any]] = []
    request = b'{"jsonrpc":"2.0","id":1,"method":"initialize"}\n'
    out = _run(request, monkeypatch, tmp_path, frames)

    assert json.loads(out) == {"jsonrpc": "2.0", "id": 1, "result": {}}
    assert frames == []


def test_malformed_line_is_forwarded_but_not_recorded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frames: list[dict[str, Any]] = []
    out = _run(b"not json\n", monkeypatch, tmp_path, frames)

    assert out == b"not json\n"
    assert frames == []


def test_server_exit_without_response_records_an_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frames: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(frames))
    request = (
        b'{"jsonrpc":"2.0","id":7,"method":"message/send",'
        b'"params":{"message":{"messageId":"m-1"}}}\n'
    )
    a2a_proxy.run_stdio(
        "echo",
        [sys.executable, "-c", "import sys; sys.stdin.readline()"],
        socket_path=str(tmp_path / "d.sock"),
        stdin=io.BytesIO(request),
        stdout=io.BytesIO(),
        env={},
    )
    assert [f["event"]["direction"] for f in frames] == ["request", "response"]
    assert frames[1]["event"]["rpc"]["error"]["message"] == "server exited"


def test_resolve_session_id_prefers_the_env() -> None:
    assert a2a_proxy.resolve_session_id({"AGENTWATCH_SESSION_ID": "s-9"}) == "s-9"
    assert a2a_proxy.resolve_session_id({}).startswith("a2a-")