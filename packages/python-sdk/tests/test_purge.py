"""Session purge tests (M9 #202, PRD 26 I5).

Purging tombstones every record of one session (payload dropped, chain links
kept) and writes a metadata-only marker; the chain stays green.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(session: str, tool: str = "Bash") -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=tool),
        outcome=Outcome.OK,
        started_at=START,
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s1", "Bash"))
    store.append(_record("s2", "Read"))
    store.append(_record("s1", "Write"))
    return store


def test_purge_tombstones_only_that_session(tmp_path: Path) -> None:
    store = _store(tmp_path)

    store.purge_session("s1")

    live = store.records()
    assert [record.tool.name for record in live if record.session_id == "s2"] == ["Read"]
    assert [record.tool.name for record in live if record.session_id == "s1"] == ["session-purge"]


def test_purge_keeps_chain_green(tmp_path: Path) -> None:
    store = _store(tmp_path)

    store.purge_session("s1")

    assert store.verify().ok
    assert sum(1 for entry in store.entries() if entry.tombstone) == 2


def test_purge_writes_a_marker_record(tmp_path: Path) -> None:
    store = _store(tmp_path)

    report = store.purge_session("s1", reason="subject request")

    assert report.found is True
    assert report.purged == 2
    marker = [r for r in store.records() if r.tool.name == "session-purge"][0]
    assert marker.tool.arguments == {"session_id": "s1", "reason": "subject request"}
    assert report.marker_seq == store.entries()[-1].seq


def test_purge_unknown_session_is_a_noop(tmp_path: Path) -> None:
    store = _store(tmp_path)
    before = store.path.read_text(encoding="utf-8")

    report = store.purge_session("nope")

    assert report.found is False
    assert report.purged == 0
    assert report.marker_seq is None
    assert store.path.read_text(encoding="utf-8") == before
    assert store.verify().ok


def test_cli_purge_requires_yes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)

    rc = main(["--set", f"store.path={store_dir}", "purge", "s1"])

    assert rc != 0
    assert "--yes" in capsys.readouterr().err


def test_cli_purge_reports(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)

    rc = main(["--set", f"store.path={store_dir}", "purge", "s1", "--yes"])

    assert rc == 0
    assert "purged 2" in capsys.readouterr().out
