"""Daemon routing for MCP proxy frames (M10 N1 #83).

The daemon normalizes ``phase == "mcp"`` frames through the proxy adapter and
appends validated records to the store, reusing dedup and the hash chain.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentwatch.daemon import Daemon
from agentwatch.store import RecordStore

FRAME: dict[str, Any] = {
    "phase": "mcp",
    "harness": "mcp-proxy",
    "event": {
        "server": "github",
        "session_id": "s-1",
        "direction": "request",
        "rpc": {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "issue_get", "arguments": {"number": 3}},
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


def test_daemon_persists_an_mcp_frame(tmp_path: Path) -> None:
    daemon = _daemon(tmp_path)

    written = daemon.handle_message(FRAME)

    assert len(written) == 1
    record = daemon.store.records()[0]
    assert record.tool.name == "issue_get"
    assert record.tool.server == "github"
    assert daemon.store.verify().ok


def test_daemon_dedups_a_repeated_mcp_frame(tmp_path: Path) -> None:
    daemon = _daemon(tmp_path)

    daemon.handle_message(FRAME)
    second = daemon.handle_message(FRAME)

    assert second == []
    assert len(daemon.store.records()) == 1


def test_daemon_quarantines_an_invalid_mcp_frame(tmp_path: Path) -> None:
    daemon = _daemon(tmp_path)

    bad = {**FRAME, "event": {**FRAME["event"], "direction": "sideways"}}
    written = daemon.handle_message(bad)

    assert written == []
    assert daemon.store.records() == []
    assert (tmp_path / "quarantine.jsonl").exists()


def test_daemon_keeps_two_calls_that_reuse_a_jsonrpc_id(tmp_path: Path) -> None:
    daemon = _daemon(tmp_path)
    first = {**FRAME, "event": {**FRAME["event"], "call_id": "c1"}}
    second = {**FRAME, "event": {**FRAME["event"], "call_id": "c2"}}

    assert len(daemon.handle_message(first)) == 1
    assert len(daemon.handle_message(second)) == 1
    assert len(daemon.store.records()) == 2
