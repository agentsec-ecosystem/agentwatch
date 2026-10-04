"""Per-step performance budget tests (M12 12.2, NFR-1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentwatch.adapters import claude_code
from agentwatch.daemon import Daemon
from agentwatch.perf import PerfStats, time_call
from agentwatch.store import RecordStore

BUDGET_MS = 5.0


def _pre_message(span: int = 1) -> dict[str, Any]:
    return {
        "phase": "pre",
        "harness": "claude-code",
        "event": {
            "session_id": "perf",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_use_id": f"perf-{span}",
            "timestamp": "2026-01-02T03:04:05+00:00",
        },
    }


def test_perf_stats_within_helper() -> None:
    stats = PerfStats(iterations=1, mean_ms=1.0, p50_ms=1.0, p99_ms=2.0, max_ms=3.0)
    assert stats.within(5.0)
    assert not stats.within(1.5)


def test_normalize_p99_is_within_budget() -> None:
    message = _pre_message()
    stats = time_call(lambda: claude_code.normalize(message), iterations=2000)

    assert stats.p99_ms <= BUDGET_MS, stats


def test_daemon_handle_message_p99_is_within_budget(tmp_path: Path) -> None:
    daemon = Daemon(
        socket_path=tmp_path / "d.sock",
        store=RecordStore(tmp_path / "records.jsonl", durability="none"),
        records_path=tmp_path / "records.jsonl",
    )
    counter = {"n": 0}

    def step() -> None:
        counter["n"] += 1
        daemon.handle_message(_pre_message(counter["n"]))

    stats = time_call(step, iterations=1000)

    assert stats.p99_ms <= BUDGET_MS, stats
    assert len(daemon.store.records()) == 1000
