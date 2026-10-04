"""Retention CLI tests (M9 R11, #76/#77).

`agentwatch retention apply` tombstones records older than store.retention_days
and must leave the hash chain green.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

NOW = datetime.now(timezone.utc)


def _record(when: datetime, tool: str) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=tool),
        outcome=Outcome.OK,
        started_at=when,
    )


def _seed(directory: Path) -> None:
    store = RecordStore(directory / "records.jsonl")
    store.append(_record(NOW - timedelta(days=100), "old"))
    store.append(_record(NOW, "new"))


def _run(directory: Path, **extra: str) -> int:
    overrides = ["--set", f"store.path={directory}", "--set", "store.retention_days=30"]
    for key, value in extra.items():
        overrides += ["--set", f"{key}={value}"]
    return main([*overrides, "retention", "apply", "--json"])


def test_retention_apply_tombstones_and_reports(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "store"
    directory.mkdir()
    _seed(directory)

    rc = _run(directory)

    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data == {
        "purged": 1,
        "kept": 1,
        "chain_ok": True,
        "broken_at": None,
        "retention_days": 30,
    }


def test_apply_retention_keeps_chain_green(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "store"
    directory.mkdir()
    _seed(directory)

    _run(directory)
    capsys.readouterr()

    store = RecordStore(directory / "records.jsonl")
    assert store.verify().ok
    assert any(entry.tombstone for entry in store.entries())
    assert {record.tool.name for record in store.records()} == {"new"}
