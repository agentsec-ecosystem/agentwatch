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
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch import hook
from agentwatch.daemon import HOOK_ERROR_TOOL, Daemon
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall, validate_record
from agentwatch.store import RecordStore

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
    records = RecordStore(records_path).records()
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
    validate_record(json.loads(lines[0])["record"])


def test_matched_post_has_no_hook_error(short_dir: Path) -> None:
    daemon, socket_path, records_path = _started(short_dir)
    try:
        hook.send(
            {"phase": "pre", "harness": "claude-code", "event": PRE}, socket_path=str(socket_path)
        )
        hook.send(
            {"phase": "post", "harness": "claude-code", "event": POST}, socket_path=str(socket_path)
        )
        _read_lines(records_path, 2)
    finally:
        daemon.stop()

    tools = [record.tool.name for record in RecordStore(records_path).records()]
    assert HOOK_ERROR_TOOL not in tools


def test_unmatched_post_records_a_hook_error(short_dir: Path) -> None:
    daemon, socket_path, records_path = _started(short_dir)
    try:
        # A Post with no preceding Pre means the intent hook was missed (F2).
        hook.send(
            {"phase": "post", "harness": "claude-code", "event": POST}, socket_path=str(socket_path)
        )
        _read_lines(records_path, 2)
    finally:
        daemon.stop()

    records = RecordStore(records_path).records()
    errors = [record for record in records if record.tool.name == HOOK_ERROR_TOOL]
    assert len(errors) == 1
    assert errors[0].outcome.value == "error"


def test_explicit_hook_error_frame_is_recorded(short_dir: Path) -> None:
    daemon, socket_path, records_path = _started(short_dir)
    event = {
        "session_id": "sess-1",
        "tool_name": "Bash",
        "tool_use_id": "call-9",
        "timestamp": "2026-01-02T03:04:05+00:00",
        "reason": "hook could not deliver",
    }
    try:
        hook.send(
            {"phase": "hook-error", "harness": "claude-code", "event": event},
            socket_path=str(socket_path),
        )
        _read_lines(records_path, 1)
    finally:
        daemon.stop()

    record = RecordStore(records_path).records()[0]
    assert record.tool.name == HOOK_ERROR_TOOL
    assert record.outcome.value == "error"
    assert record.session_id == "sess-1"


def test_bad_timestamp_frame_does_not_kill_the_daemon(short_dir: Path) -> None:
    daemon, socket_path, records_path = _started(short_dir)
    try:
        # Valid JSON, valid phase, but an unparseable timestamp must not be fatal.
        assert hook.send(
            {
                "phase": "pre",
                "harness": "claude-code",
                "event": {**PRE, "timestamp": "not-a-date"},
            },
            socket_path=str(socket_path),
        )
        assert hook.send(
            {"phase": "pre", "harness": "claude-code", "event": PRE}, socket_path=str(socket_path)
        )
        _read_lines(records_path, 2)
        alive = daemon.is_alive()
    finally:
        daemon.stop()

    assert alive, "the daemon serve thread died"
    records = RecordStore(records_path).records()
    assert any(r.session_id == "sess-1" and r.tool.name == "Bash" for r in records)
    assert any(r.tool.name == HOOK_ERROR_TOOL for r in records)


def test_second_daemon_refuses_a_live_socket(short_dir: Path) -> None:
    daemon, socket_path, _ = _started(short_dir)
    try:
        other = Daemon(socket_path=str(socket_path), records_path=short_dir / "other.jsonl")
        with pytest.raises(RuntimeError):
            other.start()
    finally:
        daemon.stop()


def test_stale_socket_file_is_replaced(short_dir: Path) -> None:
    socket_path = short_dir / "stale.sock"
    socket_path.write_text("not a socket", encoding="utf-8")
    daemon = Daemon(socket_path=str(socket_path), records_path=short_dir / "records.jsonl")
    daemon.start()
    try:
        assert daemon.is_alive()
    finally:
        daemon.stop()


def test_unpaired_pre_is_flushed_after_timeout(short_dir: Path) -> None:
    socket_path = short_dir / "d.sock"
    records_path = short_dir / "records.jsonl"
    daemon = Daemon(
        socket_path=str(socket_path),
        records_path=records_path,
        pre_timeout_seconds=0.05,
        sweep_interval_seconds=0.02,
    )
    daemon.start()
    try:
        hook.send(
            {"phase": "pre", "harness": "claude-code", "event": PRE}, socket_path=str(socket_path)
        )
        # A Pre whose Post never arrives must still be recorded as hook-error (F2).
        _read_lines(records_path, 2)
    finally:
        daemon.stop()

    records = RecordStore(records_path).records()
    assert any(r.tool.name == HOOK_ERROR_TOOL for r in records)


def _record(name: str = "Bash") -> AgentRecord:
    return AgentRecord(
        session_id="sess-chain",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=name),
        outcome=Outcome.OK,
        started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def test_daemon_records_session_boundaries(short_dir: Path) -> None:
    daemon, socket_path, records_path = _started(short_dir)
    try:
        hook.send(
            {
                "phase": "session-start",
                "harness": "claude-code",
                "event": {
                    "session_id": "sess-1",
                    "reason": "startup",
                    "timestamp": "2026-01-02T03:04:00+00:00",
                },
            },
            socket_path=str(socket_path),
        )
        _read_lines(records_path, 1)
    finally:
        daemon.stop()

    record = RecordStore(records_path).records()[0]
    assert record.tool.name == "session-start"
    assert record.tool.arguments == {"reason": "startup"}


def test_permission_denied_retires_the_pending_pre(short_dir: Path) -> None:
    daemon, socket_path, records_path = _started(short_dir)
    try:
        hook.send(
            {"phase": "pre", "harness": "claude-code", "event": PRE}, socket_path=str(socket_path)
        )
        denied_event = {**PRE, "reason": "auto-denied"}
        hook.send(
            {"phase": "denied", "harness": "claude-code", "event": denied_event},
            socket_path=str(socket_path),
        )
        _read_lines(records_path, 2)
    finally:
        daemon.stop()

    records = RecordStore(records_path).records()
    assert any(record.outcome.value == "denied" for record in records)
    assert HOOK_ERROR_TOOL not in [record.tool.name for record in records]


def test_daemon_emits_session_usage_from_transcript(short_dir: Path) -> None:
    daemon, socket_path, records_path = _started(short_dir)
    transcript = short_dir / "t.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "message": {
                    "model": "claude-x",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                    "content": [{"type": "text", "text": "CANARY-sk-abcdefgh"}],
                }
            }
        ),
        encoding="utf-8",
    )
    try:
        hook.send(
            {
                "phase": "session-end",
                "harness": "claude-code",
                "event": {
                    "session_id": "sess-1",
                    "reason": "other",
                    "timestamp": "2026-01-02T03:05:00+00:00",
                    "transcript_path": str(transcript),
                },
            },
            socket_path=str(socket_path),
        )
        _read_lines(records_path, 2)
    finally:
        daemon.stop()

    usage = [r for r in RecordStore(records_path).records() if r.tool.name == "session-usage"]
    assert usage
    assert usage[0].tokens == 15
    assert usage[0].agent.model_version == "claude-x"
    assert "CANARY" not in json.dumps(usage[0].to_dict())


def test_daemon_records_a_gap_when_a_previous_pid_exists(short_dir: Path) -> None:
    records_path = short_dir / "records.jsonl"
    store = RecordStore(records_path)
    store.append(_record("old"))
    (short_dir / "daemon.pid").write_text("12345", encoding="utf-8")
    daemon = Daemon(
        socket_path=str(short_dir / "d.sock"),
        records_path=records_path,
        store=store,
        gap_threshold_seconds=1.0,
    )
    daemon.start()
    try:
        names = [r.tool.name for r in daemon.store.records()]
    finally:
        daemon.stop()

    assert "recording-gap" in names


def test_daemon_does_not_record_a_gap_without_a_pid(short_dir: Path) -> None:
    records_path = short_dir / "records.jsonl"
    store = RecordStore(records_path)
    store.append(_record("old"))
    daemon = Daemon(
        socket_path=str(short_dir / "d.sock"),
        records_path=records_path,
        store=store,
        gap_threshold_seconds=1.0,
    )
    daemon.start()
    try:
        names = [r.tool.name for r in daemon.store.records()]
    finally:
        daemon.stop()

    assert "recording-gap" not in names


def test_records_are_persisted_in_a_hash_chained_store(short_dir: Path) -> None:
    daemon, socket_path, records_path = _started(short_dir)
    try:
        hook.send(
            {"phase": "pre", "harness": "claude-code", "event": PRE}, socket_path=str(socket_path)
        )
        hook.send(
            {"phase": "post", "harness": "claude-code", "event": POST}, socket_path=str(socket_path)
        )
        lines = _read_lines(records_path, 2)
    finally:
        daemon.stop()

    assert len(lines) == 2
    status = RecordStore(records_path).verify()
    assert status.ok is True
    assert status.checked == 2


def test_daemon_surfaces_a_broken_chain(short_dir: Path) -> None:
    socket_path = short_dir / "d.sock"
    records_path = short_dir / "records.jsonl"
    store = RecordStore(records_path)
    store.append(_record("A"))
    lines = records_path.read_text(encoding="utf-8").splitlines()
    envelope = json.loads(lines[0])
    envelope["record"]["tool"]["name"] = "Tampered"
    lines[0] = json.dumps(envelope)
    records_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    daemon = Daemon(socket_path=str(socket_path), records_path=records_path)
    daemon.start()
    try:
        assert daemon.chain_status is not None
        assert daemon.chain_status.ok is False
    finally:
        daemon.stop()


def test_store_full_fails_closed_without_dropping_or_dying(short_dir: Path) -> None:
    socket_path = short_dir / "d.sock"
    records_path = short_dir / "records.jsonl"
    store = RecordStore(records_path, max_size_mb=0)
    daemon = Daemon(socket_path=str(socket_path), records_path=records_path, store=store)
    daemon.start()
    try:
        hook.send(
            {"phase": "pre", "harness": "claude-code", "event": PRE}, socket_path=str(socket_path)
        )
        hook.send(
            {"phase": "post", "harness": "claude-code", "event": POST}, socket_path=str(socket_path)
        )
        alive = daemon.is_alive()
    finally:
        daemon.stop()

    assert alive, "the daemon died on a full store"
    assert store.size_bytes() == 0


def test_store_full_reports_no_persisted_records(short_dir: Path) -> None:
    records_path = short_dir / "records.jsonl"
    store = RecordStore(records_path, max_size_mb=0)
    daemon = Daemon(
        socket_path=str(short_dir / "d.sock"), records_path=records_path, store=store
    )

    result = daemon.handle_message({"phase": "pre", "harness": "claude-code", "event": PRE})

    assert result == []


def test_daemon_applies_retention_on_start(short_dir: Path) -> None:
    records_path = short_dir / "records.jsonl"
    store = RecordStore(records_path)
    store.append(_record("old"))  # started_at 2026-01-02, older than 1 day
    daemon = Daemon(
        socket_path=str(short_dir / "d.sock"),
        records_path=records_path,
        store=store,
        retention_days=1,
    )
    daemon.start()
    try:
        assert daemon.store.records() == []
        assert daemon.store.entries()[0].tombstone is True
    finally:
        daemon.stop()


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
