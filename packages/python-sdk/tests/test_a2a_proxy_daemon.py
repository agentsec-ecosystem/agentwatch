"""Daemon routing for A2A proxy frames (M29 A2A-1 #364).

The daemon normalizes ``phase == "a2a"`` frames through the A2A proxy adapter and
appends validated records to the store, reusing dedup and the hash chain.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentwatch.daemon import Daemon
from agentwatch.store import RecordStore

FRAME: dict[str, Any] = {
    "phase": "a2a",
    "harness": "a2a-proxy",
    "event": {
        "agent": "remote-scheduler",
        "session_id": "s-1",
        "direction": "request",
        "rpc": {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "message/send",
            "params": {"message": {"messageId": "m-1", "taskId": "t-1"}},
        },
        "timestamp": "2026-01-02T03:04:05+00:00",
    },
}


def _daemon(tmp_path: Path) -> Daemon:
    store = RecordStore(tmp_path / "records.jsonl")
    return Daemon(
        socket_path=tmp_path / "d.sock",
        store=store,
        records_path=tmp_path / "records.jsonl",
    )


def test_daemon_persists_an_a2a_frame(tmp_path: Path) -> None:
    daemon = _daemon(tmp_path)

    written = daemon.handle_message(FRAME)

    assert len(written) == 1
    record = daemon.store.records()[0]
    assert record.tool.name == "message/send"
    assert record.tool.server == "remote-scheduler"
    assert daemon.store.verify().ok


def test_daemon_dedups_a_repeated_a2a_frame(tmp_path: Path) -> None:
    daemon = _daemon(tmp_path)

    daemon.handle_message(FRAME)
    second = daemon.handle_message(FRAME)

    assert second == []
    assert len(daemon.store.records()) == 1


def test_daemon_quarantines_an_invalid_a2a_frame(tmp_path: Path) -> None:
    daemon = _daemon(tmp_path)

    bad = {**FRAME, "event": {**FRAME["event"], "direction": "sideways"}}
    written = daemon.handle_message(bad)

    assert written == []
    assert daemon.store.records() == []
    assert (tmp_path / "quarantine.jsonl").exists()