"""Fault-injection suite F1–F10 (M12 12.5/12.6, PRD 17).

Every operational failure must fail closed and surface — never silently stop.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from agentwatch.configuration import ConfigError, load_config
from agentwatch.daemon import Daemon
from agentwatch.export import ExportError, ExportOrchestrator
from agentwatch.health import HealthSnapshot
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore, StoreFullError, repair_store


def _record(*, session: str = "s1", span: str = "sp1", age_s: float = 0.0) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent-1"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=datetime.now(timezone.utc) - timedelta(seconds=age_s),
        span_id=span,
    )


def _daemon(tmp_path: Path, *, store: RecordStore | None = None) -> tuple[Daemon, HealthSnapshot]:
    health = HealthSnapshot(store_path=tmp_path / "records.jsonl")
    daemon = Daemon(
        socket_path=tmp_path / "d.sock",
        store=store or RecordStore(tmp_path / "records.jsonl"),
        records_path=tmp_path / "records.jsonl",
        health=health,
    )
    return daemon, health


def _pre(span: str = "p1", *, ts: str | None = None) -> dict[str, Any]:
    return {
        "phase": "pre",
        "harness": "claude-code",
        "event": {
            "session_id": "s1",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_use_id": span,
            "timestamp": ts or datetime.now(timezone.utc).isoformat(),
        },
    }


def test_f1_daemon_crash_records_a_gap(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record(age_s=3600))
    (tmp_path / "daemon.pid").write_text("4242", encoding="utf-8")
    daemon, health = _daemon(tmp_path, store=store)

    daemon._record_gap_if_needed()

    assert "recording-gap" in [record.tool.name for record in store.records()]
    assert health.to_dict()["reason"] == "recording-gap"


def test_f2_hook_error_is_recorded_not_dropped(tmp_path: Path) -> None:
    daemon, health = _daemon(tmp_path)

    written = daemon.handle_message(
        {"phase": "hook-error", "harness": "claude-code", "event": {"reason": "boom"}}
    )

    assert written and written[0].tool.name == "hook-error"
    assert written[0].outcome is Outcome.ERROR
    assert health.to_dict()["hooks"]["claude-code"]["errors"] == 1


def test_f3_store_full_fails_closed(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl", max_size_mb=0)
    daemon, health = _daemon(tmp_path, store=store)

    with pytest.raises(StoreFullError):
        store.append(_record())
    persisted = daemon._append(_record())

    assert persisted is None
    assert health.to_dict()["state"] == "stopped"
    assert "cap" in (health.to_dict()["reason"] or "")


def test_f4_corrupt_chain_is_stopped_and_repairable(tmp_path: Path) -> None:
    import json

    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    lines = store.path.read_text(encoding="utf-8").splitlines()
    envelope = json.loads(lines[1])
    envelope["record"]["tool"]["name"] = "Tampered"
    lines[1] = json.dumps(envelope)
    store.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    daemon, health = _daemon(tmp_path, store=store)

    health.set_chain(store.refresh())
    assert health.to_dict()["state"] == "stopped"

    assert repair_store(store.path).repaired
    assert RecordStore(store.path).verify().ok


class _FailingSink:
    def emit(self, record: AgentRecord, *, seq: int) -> None:
        raise ExportError("endpoint down")


def test_f5_export_failure_leaves_store_intact(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    orchestrator = ExportOrchestrator(store, _FailingSink())

    report = orchestrator.export_pending()

    assert report.error is not None
    assert report.exported == 0
    assert len(store.records()) == 1
    assert store.verify().ok


def test_f6_self_test_failure_blocks_export(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    orchestrator = ExportOrchestrator(store, _FailingSink(), self_test=lambda: False)

    report = orchestrator.export_pending()

    assert report.blocked
    assert report.exported == 0


def test_f7_bad_config_fails_closed() -> None:
    with pytest.raises(ConfigError):
        load_config(cli_overrides={"nope.key": "1"})


def test_f8_normalize_error_is_quarantined_and_recorded(tmp_path: Path) -> None:
    daemon, _ = _daemon(tmp_path)
    bad: dict[str, Any] = {"phase": "pre", "harness": "claude-code", "event": "not-an-object"}

    written = daemon.handle_message(bad)

    assert written and written[0].tool.name == "hook-error"
    assert (tmp_path / "quarantine.jsonl").exists()


def test_f9_clock_skew_is_flagged(tmp_path: Path) -> None:
    daemon, health = _daemon(tmp_path)
    future = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()

    daemon.handle_message(_pre(ts=future))

    assert health.to_dict()["reason"] == "clock-skew"


def test_f10_partial_session_is_surfaced(tmp_path: Path) -> None:
    daemon, _ = _daemon(tmp_path)

    daemon.handle_message(_pre(span="lonely"))
    daemon._sweep_pending_pre(force=True)

    names = [record.tool.name for record in daemon.store.records()]
    assert "hook-error" in names
