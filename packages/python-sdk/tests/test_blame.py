"""`agentwatch blame` tests (M17 S18, #246).

Reverse index per path: newest first, exact vs heuristic labelled, normalized
against the project root, and never falsely matching an outside-project path.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.blame import build_blame, normalize_path, render_blame
from agentwatch.cli.main import main
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _rec(
    session: str,
    tool: str,
    arguments: dict[str, object],
    *,
    minute: int,
    project: str | None,
    span: str,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity=f"agent-{session}"),
        tool=ToolCall(name=tool, arguments=arguments),
        outcome=Outcome.OK,
        started_at=START + timedelta(minutes=minute),
        harness="claude-code",
        project=project,
        span_id=span,
        step_type=StepType.ACT,
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        _rec("s1", "Write", {"file_path": "/repo/a.py"}, minute=0, project="/repo", span="1")
    )
    store.append(
        _rec("s2", "Edit", {"file_path": "/repo/a.py"}, minute=5, project="/repo", span="2")
    )
    store.append(
        _rec("s2", "Bash", {"command": "cp src.py ./a.py"}, minute=6, project="/repo", span="3")
    )
    store.append(
        _rec("s3", "Write", {"file_path": "/other/a.py"}, minute=7, project="/other", span="4")
    )
    return store


def test_blame_lists_newest_first_and_labels_confidence(tmp_path: Path) -> None:
    store = _store(tmp_path)

    report = build_blame(store, "/repo/a.py")

    assert [hit.session_id for hit in report.hits] == ["s2", "s2", "s1"]
    assert report.hits[0].confidence == "heuristic"  # shell cp
    assert report.hits[1].confidence == "exact"  # structured Edit
    assert report.sessions == ("s2", "s1")


def test_blame_normalizes_relative_query_against_project(tmp_path: Path) -> None:
    store = _store(tmp_path)

    report = build_blame(store, "a.py", project="/repo")

    assert report.normalized == "/repo/a.py"
    assert len(report.hits) == 3


def test_blame_does_not_match_outside_project(tmp_path: Path) -> None:
    store = _store(tmp_path)

    report = build_blame(store, "/repo/a.py")

    assert all(hit.session_id != "s3" for hit in report.hits)


def test_normalize_path_handles_home_and_dotdot() -> None:
    assert normalize_path("~/x/../y", project=None).endswith("/y")
    assert normalize_path("b/../a.py", project="/repo") == "/repo/a.py"


def test_blame_project_filter(tmp_path: Path) -> None:
    store = _store(tmp_path)

    report = build_blame(store, "/repo/a.py", project="/other")

    assert report.hits == ()


def test_render_blame_empty(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    assert "no records touched" in render_blame(build_blame(store, "/x"))


def test_cli_blame_json_and_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = _store(tmp_path)
    import shutil

    shutil.copy(store.path, store_dir / "records.jsonl")

    rc = main(["--set", f"store.path={store_dir}", "blame", "/repo/a.py", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["hits"]) == 3

    rc = main(["--set", f"store.path={store_dir}", "blame", "/repo/a.py", "--sessions"])
    assert rc == 0
    assert "s2" in capsys.readouterr().out
