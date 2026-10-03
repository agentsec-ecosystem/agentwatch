"""Tests for hook installation and daemon lifecycle (M3 #159).

``agentwatch init`` writes Claude Code hook entries into a settings file and
starts the local daemon; ``agentwatch uninstall`` reverses both. These tests
exercise the real settings file contract and a real daemon subprocess.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import agentwatch
from agentwatch import hook
from agentwatch.install import (
    HookCommand,
    InstallError,
    daemon_paths,
    hooks_installed,
    install_hooks,
    is_daemon_alive,
    resolve_hook_command,
    resolve_scope,
    start_daemon,
    stop_daemon,
    uninstall_hooks,
)
from agentwatch.store import RecordStore

# A fixed, hand-written command so expected JSON is derived independently of
# the resolver under test.
HOOK = HookCommand(command="/opt/aw/bin/agentwatch-hook", args_prefix=())


def _read(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _handler(phase: str) -> dict[str, object]:
    return {"type": "command", "command": HOOK.command, "args": [phase]}


def _group(phase: str) -> dict[str, object]:
    return {"matcher": "*", "hooks": [_handler(phase)]}


# ---------------------------------------------------------------------------
# Settings contract
# ---------------------------------------------------------------------------


def test_install_hooks_writes_exec_handlers_for_each_tool_event(tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.local.json"

    install_hooks(settings, HOOK)

    data = _read(settings)
    hooks = data["hooks"]
    assert isinstance(hooks, dict)
    assert hooks["PreToolUse"] == [_group("pre")]
    assert hooks["PostToolUse"] == [_group("post")]
    assert hooks["PostToolUseFailure"] == [_group("post")]


def test_install_hooks_wires_session_boundaries(tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.local.json"

    install_hooks(settings, HOOK)

    hooks = _read(settings)["hooks"]
    assert isinstance(hooks, dict)
    start = {"type": "command", "command": HOOK.command, "args": ["session-start"]}
    end = {"type": "command", "command": HOOK.command, "args": ["session-end"]}
    assert hooks["SessionStart"] == [{"matcher": "*", "hooks": [start]}]
    assert hooks["SessionEnd"] == [{"matcher": "*", "hooks": [end]}]


def test_install_hooks_preserves_unrelated_settings(tmp_path: Path) -> None:
    settings = tmp_path / "settings.local.json"
    unrelated = {"matcher": "Bash", "hooks": [{"type": "command", "command": "other-tool"}]}
    settings.write_text(
        json.dumps({"model": "opus", "hooks": {"PreToolUse": [unrelated]}}), encoding="utf-8"
    )

    install_hooks(settings, HOOK)

    data = _read(settings)
    assert data["model"] == "opus"
    hooks = data["hooks"]
    assert isinstance(hooks, dict)
    assert unrelated in hooks["PreToolUse"]


def test_install_hooks_is_idempotent(tmp_path: Path) -> None:
    settings = tmp_path / "settings.local.json"

    install_hooks(settings, HOOK)
    install_hooks(settings, HOOK)

    hooks = _read(settings)["hooks"]
    assert isinstance(hooks, dict)
    assert len(hooks["PreToolUse"]) == 1
    assert len(hooks["PostToolUse"]) == 1
    assert len(hooks["PostToolUseFailure"]) == 1


def test_install_hooks_replaces_a_stale_agentwatch_handler(tmp_path: Path) -> None:
    settings = tmp_path / "settings.local.json"
    stale = {
        "matcher": "*",
        "hooks": [{"type": "command", "command": "/old/bin/agentwatch-hook", "args": ["pre"]}],
    }
    settings.write_text(json.dumps({"hooks": {"PreToolUse": [stale]}}), encoding="utf-8")

    install_hooks(settings, HOOK)

    hooks = _read(settings)["hooks"]
    assert isinstance(hooks, dict)
    assert hooks["PreToolUse"] == [_group("pre")]


def test_install_hooks_refuses_malformed_settings(tmp_path: Path) -> None:
    settings = tmp_path / "settings.local.json"
    settings.write_text("{not json", encoding="utf-8")

    with pytest.raises(InstallError):
        install_hooks(settings, HOOK)

    assert settings.read_text(encoding="utf-8") == "{not json"


def test_uninstall_hooks_removes_only_agentwatch_handlers(tmp_path: Path) -> None:
    settings = tmp_path / "settings.local.json"
    unrelated = {"matcher": "Bash", "hooks": [{"type": "command", "command": "other-tool"}]}
    install_hooks(settings, HOOK)
    data = _read(settings)
    hooks = data["hooks"]
    assert isinstance(hooks, dict)
    hooks["PreToolUse"].append(unrelated)
    settings.write_text(json.dumps(data), encoding="utf-8")

    removed = uninstall_hooks(settings)

    assert removed is True
    after = _read(settings)
    assert unrelated in after["hooks"]["PreToolUse"]
    assert after["hooks"].get("PostToolUse") is None


def test_uninstall_hooks_missing_file_is_noop(tmp_path: Path) -> None:
    assert uninstall_hooks(tmp_path / "absent.json") is False


def test_hooks_installed_detects_installed_hooks(tmp_path: Path) -> None:
    settings = tmp_path / "settings.local.json"
    assert hooks_installed(settings) is False

    install_hooks(settings, HOOK)

    assert hooks_installed(settings) is True


def test_install_hooks_rejects_non_object_settings(tmp_path: Path) -> None:
    settings = tmp_path / "settings.local.json"
    settings.write_text("[]", encoding="utf-8")

    with pytest.raises(InstallError):
        install_hooks(settings, HOOK)


def test_resolve_scope_project_is_default_target(tmp_path: Path) -> None:
    target = resolve_scope("project", cwd=tmp_path, home=tmp_path / "home")

    assert target.scope == "project"
    assert target.settings_path == tmp_path / ".claude" / "settings.local.json"


def test_resolve_scope_user_targets_user_settings(tmp_path: Path) -> None:
    target = resolve_scope("user", cwd=tmp_path, home=tmp_path / "home")

    assert target.scope == "user"
    assert target.settings_path == tmp_path / "home" / ".claude" / "settings.json"


def test_default_hook_command_forwards_over_the_socket(short_dir: Path) -> None:
    # Exercise the real resolved entry point (sibling script or -m fallback):
    # it must connect and forward the framed message, not merely exit 0.
    socket_path = short_dir / "hook.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(socket_path))
    server.listen(1)
    received: list[bytes] = []

    def _accept() -> None:
        conn, _ = server.accept()
        with conn:
            received.append(conn.recv(65536))

    thread = threading.Thread(target=_accept, daemon=True)
    thread.start()
    try:
        command = resolve_hook_command()
        src = Path(agentwatch.__file__).resolve().parents[1]
        env = {
            **os.environ,
            "PYTHONPATH": str(src),
            "AGENTWATCH_SOCKET": str(socket_path),
        }
        event = {"session_id": "s-live", "tool_name": "Bash", "tool_use_id": "c1"}

        result = subprocess.run(
            [command.command, *command.args_prefix, "pre"],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
            check=False,
        )
        thread.join(timeout=5)
    finally:
        server.close()

    assert result.returncode == 0
    assert received, "the hook did not connect to the socket"
    message = json.loads(received[0].decode("utf-8"))
    assert message["phase"] == "pre"
    assert message["event"]["session_id"] == "s-live"


# ---------------------------------------------------------------------------
# Daemon lifecycle
# ---------------------------------------------------------------------------


@pytest.fixture
def short_dir() -> Iterator[Path]:
    # AF_UNIX paths are length-limited; keep the socket directory short.
    directory = Path(tempfile.mkdtemp(prefix="awi-", dir="/tmp"))
    yield directory
    shutil.rmtree(directory, ignore_errors=True)


def _isolate_daemon(short_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store = short_dir / "store"
    monkeypatch.setenv("AGENTWATCH_SOCKET", str(short_dir / "d.sock"))
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(store))
    monkeypatch.setenv("HOME", str(short_dir / "home"))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.chdir(short_dir)
    return store


def _read_lines(path: Path, count: int, timeout: float = 5.0) -> list[str]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            if len(lines) >= count:
                return lines
        time.sleep(0.05)
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def test_is_daemon_alive_false_without_a_daemon(
    short_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolate_daemon(short_dir, monkeypatch)
    assert is_daemon_alive() is False


def test_start_daemon_records_a_hook_and_stops(
    short_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _isolate_daemon(short_dir, monkeypatch)
    assert start_daemon() is True
    try:
        assert is_daemon_alive() is True
        assert hook.send(
            {
                "phase": "pre",
                "harness": "claude-code",
                "event": {
                    "session_id": "sess-live",
                    "tool_name": "Bash",
                    "tool_use_id": "call-live",
                    "timestamp": "2026-01-02T03:04:05+00:00",
                },
            }
        )
        lines = _read_lines(store / "records.jsonl", 1)
    finally:
        assert stop_daemon() is True

    assert RecordStore(store / "records.jsonl").records()[0].session_id == "sess-live"
    assert json.loads(lines[0])  # the sink is a non-empty JSONL envelope
    assert is_daemon_alive() is False


def test_start_daemon_is_idempotent(
    short_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolate_daemon(short_dir, monkeypatch)
    assert start_daemon() is True
    try:
        assert start_daemon() is False
    finally:
        stop_daemon()


def test_stop_daemon_without_a_daemon_is_false(
    short_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolate_daemon(short_dir, monkeypatch)
    assert stop_daemon() is False


def test_daemon_paths_live_under_the_store(
    short_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _isolate_daemon(short_dir, monkeypatch)

    paths = daemon_paths()

    assert paths.records == store / "records.jsonl"
    assert paths.pid == store / "daemon.pid"
    assert paths.log == store / "daemon.log"
    assert paths.socket == short_dir / "d.sock"


def test_entry_point_module_is_importable() -> None:
    # The daemon is spawned as ``python -m agentwatch.daemon``; guard the module.
    src = Path(agentwatch.__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(src)}
    result = subprocess.run(
        [sys.executable, "-c", "import agentwatch.daemon"],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
