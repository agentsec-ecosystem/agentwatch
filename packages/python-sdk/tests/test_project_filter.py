"""Per-project session filtering tests (M9 #201, PRD 25 I4).

Records carry the event cwd as ``project``; sessions/search/tail accept an
exact project filter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agentwatch.query import search
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore
from agentwatch.tail import Tail
from agentwatch.view import list_sessions

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(session: str, project: str | None, *, tool: str = "Bash") -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=tool),
        outcome=Outcome.OK,
        started_at=START,
        project=project,
    )


def _store(tmp_path: Path, records: list[AgentRecord]) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    for record in records:
        store.append(record)
    return store


def test_list_sessions_filters_by_project(tmp_path: Path) -> None:
    store = _store(tmp_path, [_record("s1", "/repo/a"), _record("s2", "/repo/b")])

    assert list_sessions(store, project="/repo/a") == ["s1"]
    assert list_sessions(store, project="/repo/b") == ["s2"]


def test_project_filter_is_per_record_not_per_session(tmp_path: Path) -> None:
    # One session spanning two cwds (a `cd` mid-session) links to both projects.
    store = _store(tmp_path, [_record("s1", "/repo/a"), _record("s1", "/repo/b")])

    assert list_sessions(store, project="/repo/a") == ["s1"]
    assert list_sessions(store, project="/repo/b") == ["s1"]


def test_project_filter_excludes_missing_cwd(tmp_path: Path) -> None:
    store = _store(tmp_path, [_record("s1", None)])

    assert list_sessions(store, project="/repo/a") == []
    assert list_sessions(store) == ["s1"]


def test_search_filters_by_project(tmp_path: Path) -> None:
    store = _store(tmp_path, [_record("s1", "/repo/a"), _record("s2", "/repo/b")])

    results = search(store, project="/repo/a")

    assert [record.session_id for record in results] == ["s1"]


def test_tail_filters_by_project(tmp_path: Path) -> None:
    store = _store(tmp_path, [_record("s1", "/repo/a"), _record("s2", "/repo/b")])

    lines = Tail(store.path, project="/repo/a").read_new()

    records = [line.record for line in lines if line.record is not None]
    assert [record.session_id for record in records] == ["s1"]
