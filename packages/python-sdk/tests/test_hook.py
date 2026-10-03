"""Tests for the Claude Code hook client (M3 #25).

The hook is fire-and-forget: it frames one newline-delimited JSON message and
must return 0 on every path so it never blocks the agent (F2).
"""

from __future__ import annotations

import json
import shutil
import socket
import tempfile
import threading
import time
from io import StringIO
from pathlib import Path

import pytest

from agentwatch import hook

EVENT = {
    "session_id": "sess-1",
    "tool_name": "Bash",
    "tool_input": {"cmd": "ls"},
    "tool_use_id": "call-1",
}


def _serve_once(path: Path, received: list[bytes]) -> threading.Thread:
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    server.listen(1)

    def run() -> None:
        conn, _ = server.accept()
        data = b""
        while not data.endswith(b"\n"):
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
        received.append(data)
        conn.close()
        server.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def test_sends_a_framed_message_to_the_daemon() -> None:
    # AF_UNIX paths are capped (~104 chars), so use a short directory.
    short_dir = Path(tempfile.mkdtemp(prefix="aw-", dir="/tmp"))
    path = short_dir / "s.sock"
    received: list[bytes] = []
    try:
        thread = _serve_once(path, received)
        rc = hook.main(["pre"], stdin=StringIO(json.dumps(EVENT)), socket_path=str(path))
        thread.join(timeout=2)
    finally:
        shutil.rmtree(short_dir, ignore_errors=True)

    assert rc == 0
    assert received, "the hook sent nothing"
    message = json.loads(received[0].decode("utf-8"))
    assert message == {"phase": "pre", "harness": "claude-code", "event": EVENT}


def test_malformed_stdin_sends_a_hook_error_frame() -> None:
    short_dir = Path(tempfile.mkdtemp(prefix="aw-", dir="/tmp"))
    path = short_dir / "s.sock"
    received: list[bytes] = []
    try:
        thread = _serve_once(path, received)
        rc = hook.main(["pre"], stdin=StringIO("not json"), socket_path=str(path))
        thread.join(timeout=2)
    finally:
        shutil.rmtree(short_dir, ignore_errors=True)

    assert rc == 0
    assert received, "the hook sent nothing"
    message = json.loads(received[0].decode("utf-8"))
    assert message["phase"] == "hook-error"
    assert message["harness"] == "claude-code"


def test_missing_daemon_still_exits_zero(tmp_path: Path) -> None:
    rc = hook.main(
        ["post"],
        stdin=StringIO(json.dumps(EVENT)),
        socket_path=str(tmp_path / "no-such.sock"),
    )
    assert rc == 0


def test_malformed_stdin_still_exits_zero(tmp_path: Path) -> None:
    rc = hook.main(["pre"], stdin=StringIO("not json"), socket_path=str(tmp_path / "x.sock"))
    assert rc == 0


def test_unknown_phase_still_exits_zero(tmp_path: Path) -> None:
    rc = hook.main(["sideways"], stdin=StringIO(json.dumps(EVENT)), socket_path=str(tmp_path / "x"))
    assert rc == 0


def test_no_arguments_still_exits_zero() -> None:
    assert hook.main([], stdin=StringIO("{}")) == 0


def test_default_socket_path_prefers_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTWATCH_SOCKET", "/custom/aw.sock")
    assert hook.default_socket_path() == "/custom/aw.sock"


def test_default_socket_path_uses_xdg_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTWATCH_SOCKET", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    assert hook.default_socket_path() == "/run/user/1000/agentwatch.sock"


def test_default_socket_path_falls_back_to_tmp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTWATCH_SOCKET", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    assert hook.default_socket_path() == "/tmp/agentwatch.sock"


def test_hook_spools_when_daemon_is_down(tmp_path: Path) -> None:
    from agentwatch.spool import Spool

    socket_path = tmp_path / "nope.sock"

    rc = hook.main(["pre"], stdin=StringIO(json.dumps(EVENT)), socket_path=str(socket_path))

    assert rc == 0
    lines = Spool(str(socket_path) + ".spool").drain()
    assert lines
    assert json.loads(lines[0])["phase"] == "pre"


def test_hook_latency_is_bounded() -> None:
    """The fire-and-forget hook must return quickly (async install = non-blocking)."""
    directory = Path(tempfile.mkdtemp(prefix="awh-", dir="/tmp"))
    try:
        socket_path = directory / "h.sock"
        received: list[bytes] = []
        thread = _serve_once(socket_path, received)

        start = time.perf_counter()
        rc = hook.main(["pre"], stdin=StringIO(json.dumps(EVENT)), socket_path=str(socket_path))
        elapsed = time.perf_counter() - start
        thread.join(timeout=2)
    finally:
        shutil.rmtree(directory, ignore_errors=True)

    assert rc == 0
    assert received
    assert elapsed < 2.0
