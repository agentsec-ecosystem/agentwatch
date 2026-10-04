"""Tests for session replay (M5 5.2/5.6/5.7)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli import main
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.replay import replay_session
from agentwatch.store import RecordStore

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _record(session: str, name: str, when: datetime) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=name),
        outcome=Outcome.OK,
        started_at=when,
    )


def test_replay_orders_by_time_then_chain(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s", "second", _T0 + timedelta(seconds=2)))
    store.append(_record("s", "first", _T0 + timedelta(seconds=1)))
    store.append(_record("other", "x", _T0))

    assert [r.tool.name for r in replay_session(store, "s")] == ["first", "second"]


def test_replay_unknown_session_is_empty(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s", "a", _T0))

    assert replay_session(store, "nope") == []


def test_replay_matches_the_stored_records(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    for index in range(3):
        store.append(_record("s", f"t{index}", _T0 + timedelta(seconds=index)))

    replayed = [r.to_dict() for r in replay_session(store, "s")]
    stored = [r.to_dict() for r in store.records() if r.session_id == "s"]

    assert replayed == stored


def test_cli_replay_prints_the_timeline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s", "Bash", _T0))

    rc = main(["--set", f"store.path={tmp_path}", "replay", "s"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "Bash" in out


def test_cli_replay_unknown_session_exits_nonzero(tmp_path: Path) -> None:
    rc = main(["--set", f"store.path={tmp_path}", "replay", "nope"])

    assert rc != 0
