"""Clock-skew flagging tests (M12 F9)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agentwatch.daemon import Daemon
from agentwatch.health import HealthSnapshot
from agentwatch.store import RecordStore


def _daemon(tmp_path: Path, *, tolerance: float = 60.0) -> tuple[Daemon, HealthSnapshot]:
    health = HealthSnapshot(store_path=tmp_path / "records.jsonl")
    daemon = Daemon(
        socket_path=tmp_path / "d.sock",
        store=RecordStore(tmp_path / "records.jsonl"),
        records_path=tmp_path / "records.jsonl",
        health=health,
        clock_skew_tolerance_seconds=tolerance,
    )
    return daemon, health


def _frame(timestamp: str) -> dict[str, Any]:
    return {
        "phase": "pre",
        "harness": "claude-code",
        "event": {
            "session_id": "s1",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "timestamp": timestamp,
        },
    }


def test_future_event_is_flagged_and_degrades_health(tmp_path: Path) -> None:
    daemon, health = _daemon(tmp_path)
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    written = daemon.handle_message(_frame(future))

    assert written
    payload = health.to_dict()
    assert payload["clock_skew_s"] is not None
    assert payload["clock_skew_s"] > 3600
    assert payload["state"] == "degraded"
    assert payload["reason"] == "clock-skew"
    assert payload["gaps"][0]["reason"] == "clock-skew"


def test_normal_event_is_not_flagged(tmp_path: Path) -> None:
    daemon, health = _daemon(tmp_path)
    now = datetime.now(timezone.utc).isoformat()

    daemon.handle_message(_frame(now))

    payload = health.to_dict()
    assert payload["clock_skew_s"] is None
    assert payload["state"] == "recording"
