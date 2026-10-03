"""Resumed/forked session correlation tests (M9 #200, PRD 25 I3).

Replay follows the parent-session chain so one logical conversation replays as
one timeline, guarded against cycles.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.replay import replay_session
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(
    session: str,
    *,
    offset: int = 0,
    parent: str | None = None,
    tool: str = "Bash",
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=tool),
        outcome=Outcome.OK,
        started_at=START + timedelta(seconds=offset),
        parent_session_id=parent,
    )


def _store(tmp_path: Path, records: list[AgentRecord]) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    for record in records:
        store.append(record)
    return store


def test_replay_follows_parent_into_one_timeline(tmp_path: Path) -> None:
    store = _store(
        tmp_path,
        [
            _record("sess-parent", offset=0, tool="Bash"),
            _record("sess-child", offset=1, parent="sess-parent", tool="Read"),
        ],
    )

    records = replay_session(store, "sess-child")

    assert [(r.session_id, r.tool.name) for r in records] == [
        ("sess-parent", "Bash"),
        ("sess-child", "Read"),
    ]


def test_replay_without_following_parents_is_local(tmp_path: Path) -> None:
    store = _store(
        tmp_path,
        [
            _record("sess-parent", offset=0),
            _record("sess-child", offset=1, parent="sess-parent"),
        ],
    )

    records = replay_session(store, "sess-child", follow_parents=False)

    assert [r.session_id for r in records] == ["sess-child"]


def test_replay_guards_against_parent_cycle(tmp_path: Path) -> None:
    store = _store(
        tmp_path,
        [
            _record("a", offset=0, parent="b"),
            _record("b", offset=1, parent="a"),
        ],
    )

    records = replay_session(store, "a")

    assert {r.session_id for r in records} == {"a", "b"}
