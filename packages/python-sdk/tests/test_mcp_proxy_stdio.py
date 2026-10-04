"""stdio relay tests for the MCP proxy (M10 N1 #83)."""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from agentwatch import hook, mcp_proxy

ECHO = Path(__file__).resolve().parent / "fixtures" / "mcp" / "echo_server.py"


def _capture(sent: list[dict[str, Any]]) -> Callable[..., bool]:
    """A typed replacement for ``hook.send`` that records frames."""

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
    mcp_proxy.run_stdio(
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
    request = b'{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"echo"}}\n'
    out = _run(request, monkeypatch, tmp_path, frames)
    assert json.loads(out)["result"] == {"echo": "echo"}
    assert [f["event"]["direction"] for f in frames] == ["request", "response"]


def test_forwards_lines_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    frames: list[dict[str, Any]] = []
    request = b'{"jsonrpc":"2.0","id":1,"method":"initialize"}\n'
    out = _run(request, monkeypatch, tmp_path, frames)
    assert json.loads(out) == {"jsonrpc": "2.0", "id": 1, "result": {}}
    assert frames == []  # non-tools/call not recorded


def test_malformed_line_is_forwarded_but_not_recorded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frames: list[dict[str, Any]] = []
    out = _run(b"not json\n", monkeypatch, tmp_path, frames)
    assert out == b"not json\n"
    assert frames == []


def test_line_without_trailing_newline_is_forwarded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frames: list[dict[str, Any]] = []
    request = b'{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"echo"}}'
    out = _run(request, monkeypatch, tmp_path, frames)
    assert json.loads(out)["result"] == {"echo": "echo"}
    assert len(frames) == 2


def test_server_exit_without_response_records_an_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frames: list[dict[str, Any]] = []
    monkeypatch.setattr(hook, "send", _capture(frames))
    request = b'{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"echo"}}\n'
    mcp_proxy.run_stdio(
        "echo",
        [sys.executable, "-c", "import sys; sys.stdin.readline()"],
        socket_path=str(tmp_path / "d.sock"),
        stdin=io.BytesIO(request),
        stdout=io.BytesIO(),
        env={},
    )
    assert [f["event"]["direction"] for f in frames] == ["request", "response"]
    assert frames[1]["event"]["rpc"]["error"]["message"] == "server exited"
