"""Tests for the agentwatch daemon (M3 #26).

The daemon accepts hook frames over a Unix domain socket, normalizes them, and
appends validated records to a JSONL sink.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from agentwatch import hook
from agentwatch.daemon import Daemon
from agentwatch.records import validate_record

PRE = {
    "session_id": "sess-1",
    "tool_name": "Bash",
    "tool_input": {"cmd": "ls"},
    "tool_use_id": "call-1",
    "timestamp": "2026-01-02T03:04:05+00:00",
    "agent": "triage",
}
POST = {
    **PRE,
    "timestamp": "2026-01-02T03:04:05.120000+00:00",
    "duration_ms": 12.5,
    "tool_response": {"ok": True},
}


@pytest.fixture
def short_dir() -> Iterator[Path]:
    # AF_UNIX paths are length-limited; keep the socket directory short.
    directory = Path(tempfile.mkdtemp(prefix="awd-", dir="/tmp"))
    yield directory
    shutil.rmtree(directory, ignore_errors=True)


def _read_lines(path: Path, count: int, timeout: float = 3.0) -> list[str]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            if len(lines) >= count:
                return lines
        time.sleep(0.02)
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def _send_raw(socket_path: Path, payload: bytes) -> None:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(str(socket_path))
        sock.sendall(payload)
    finally:
        sock.close()


def _started(short_dir: Path) -> tuple[Daemon, Path, Path]:
    socket_path = short_dir / "d.sock"
    records_path = short_dir / "records.jsonl"
    daemon = Daemon(socket_path=str(socket_path), records_path=records_path)
    daemon.start()
    return daemon, socket_path, records_path


def test_hook_to_daemon_round_trip_appends_valid_records(short_dir: Path) -> None:
    daemon, socket_path, records_path = _started(short_dir)
    try:
        assert hook.send(
            {"phase": "pre", "harness": "claude-code", "event": PRE}, socket_path=str(socket_path)
        )
        assert hook.send(
            {"phase": "post", "harness": "claude-code", "event": POST}, socket_path=str(socket_path)
        )
        lines = _read_lines(records_path, 2)
    finally:
        daemon.stop()

    assert len(lines) == 2
    records = [validate_record(json.loads(line)) for line in lines]
    assert records[0].session_id == "sess-1"
    assert records[1].outcome.value == "ok"
    assert records[0].span_id == records[1].span_id == "call-1"


def test_socket_is_owner_only(short_dir: Path) -> None:
    daemon, socket_path, _ = _started(short_dir)
    try:
        mode = os.stat(socket_path).st_mode & 0o777
    finally:
        daemon.stop()
    assert mode == 0o600


def test_malformed_line_does_not_kill_the_daemon(short_dir: Path) -> None:
    daemon, socket_path, records_path = _started(short_dir)
    try:
        _send_raw(socket_path, b"not json at all\n")
        assert hook.send(
            {"phase": "pre", "harness": "claude-code", "event": PRE}, socket_path=str(socket_path)
        )
        lines = _read_lines(records_path, 1)
    finally:
        daemon.stop()

    assert len(lines) == 1
    validate_record(json.loads(lines[0]))


def test_invalid_adapter_message_is_ignored(short_dir: Path) -> None:
    daemon, socket_path, records_path = _started(short_dir)
    try:
        # Valid JSON, unsupported phase: rejected, not written, daemon survives.
        assert hook.send(
            {"phase": "sideways", "harness": "claude-code", "event": PRE},
            socket_path=str(socket_path),
        )
        assert hook.send(
            {"phase": "pre", "harness": "claude-code", "event": PRE}, socket_path=str(socket_path)
        )
        lines = _read_lines(records_path, 1)
    finally:
        daemon.stop()

    assert len(lines) == 1
