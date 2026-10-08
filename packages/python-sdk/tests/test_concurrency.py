"""CNC-1 concurrency report + `ambiguous` provenance tests (M30 #474, PRD 57).

Parallel/worktree/background agents edit the same paths; `blame`/`at` show no
overlap. `concurrency` reports sessions overlapping in time on the same
repo/path and shared-file edits; `provenance` marks multi-session ranges
`ambiguous` instead of picking one.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.concurrency import build_concurrency, render_concurrency
from agentwatch.provenance import (
    CommitFacts,
    LineRange,
    build_provenance,
    capture_ranges,
    to_attribution_arguments,
)
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

FIXTURE = Path(__file__).parent / "fixtures" / "provenance" / "two_sessions.jsonl"
BASE = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_two_session_fixture_reports_overlap_and_shared_file() -> None:
    store = RecordStore(FIXTURE)

    report = build_concurrency(store, project="/repo")

    assert len(report.overlaps) == 1
    assert report.overlaps[0].sessions == ("s1", "s2")
    assert report.overlaps[0].paths == ("/repo/app.py",)
    shared = {entry.path: entry for entry in report.shared_files}
    assert shared["/repo/app.py"].sessions == ("s1", "s2")
    assert shared["/repo/app.py"].edits == 2
    assert "/repo/other.py" not in shared  # only one session touched it


def test_disjoint_sessions_do_not_overlap(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    for session, offset in (("a", 0), ("b", 120)):
        store.append(
            AgentRecord(
                session_id=session,
                agent=AgentIdentity(identity=session),
                tool=ToolCall(name="Edit", arguments={"file_path": "/repo/app.py"}),
                outcome=Outcome.OK,
                started_at=BASE + timedelta(minutes=offset),
                ended_at=BASE + timedelta(minutes=offset + 5),
                project="/repo",
            )
        )

    report = build_concurrency(store, project="/repo")

    assert report.overlaps == ()
    assert report.shared_files[0].sessions == ("a", "b")


def test_render_concurrency_summarizes_overlaps() -> None:
    store = RecordStore(FIXTURE)

    text = render_concurrency(build_concurrency(store, project="/repo"))

    assert "s1" in text and "s2" in text
    assert "/repo/app.py" in text


def test_multi_session_range_is_ambiguous(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    for session in ("s1", "s2"):
        capture = capture_ranges(
            {"file_path": "/repo/app.py", "start_line": 1, "end_line": 3, "new_string": "x"},
            tool_name="Edit",
        )
        store.append(
            AgentRecord(
                session_id=session,
                agent=AgentIdentity(identity=session),
                tool=ToolCall(name="Edit", arguments=to_attribution_arguments(capture)),
                outcome=Outcome.OK,
                started_at=BASE,
                project="/repo",
            )
        )

    class FakeGit:
        available = True

        def commit_facts(self, revision: str) -> CommitFacts:
            return CommitFacts(
                requested=revision,
                revision=revision,
                available=True,
                paths=("app.py",),
                ranges={"app.py": (LineRange(1, 3),)},
                committed_at=BASE + timedelta(minutes=1),
            )

        def pr_commit(self, number: int) -> str | None:
            return None

    report = build_provenance(store, "abc1234", repo="/repo", git=FakeGit())

    ambiguous = [line_range for line_range in report.ranges if line_range.confidence == "ambiguous"]
    assert ambiguous, report.to_dict()
    assert report.ambiguous is True
    assert set(ambiguous[0].sessions) == {"s1", "s2"}


def test_cli_concurrency_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    shutil.copy(FIXTURE, store_dir / "records.jsonl")

    rc = main(["--set", f"store.path={store_dir}", "concurrency", "--project", "/repo", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["overlaps"][0]["sessions"] == ["s1", "s2"]
