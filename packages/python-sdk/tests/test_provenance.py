"""PRV-1 `provenance` tests (M30 #462, PRD 53).

Code provenance joins git facts to the records that produced them with a
per-range confidence. The hard honesty rules: a commit with no recorded session
says "no recorded agent activity" (never "human"), hand-edited-after-agent
ranges are `mixed`, and gaps are flagged.
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.provenance import (
    CommitFacts,
    LineRange,
    build_provenance,
    parse_target,
    to_attribution_arguments,
)
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Approval,
    Authorization,
    AuthorizationSource,
    Outcome,
    ToolCall,
)
from agentwatch.store import RecordStore

BASE = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)


class FakeGit:
    """An in-memory git fact source (deterministic, offline)."""

    def __init__(self, facts: dict[str, CommitFacts], *, prs: dict[int, str] | None = None):
        self._facts = facts
        self._prs = prs or {}
        self.available = True

    def commit_facts(self, revision: str) -> CommitFacts:
        if revision in self._facts:
            return self._facts[revision]
        return CommitFacts(requested=revision, revision=None, available=True)

    def pr_commit(self, number: int) -> str | None:
        return self._prs.get(number)


def _record(
    session: str,
    tool: str,
    arguments: dict[str, object],
    *,
    minute: int,
    project: str = "/repo",
    authorization: Authorization | None = None,
    environment: dict[str, object] | None = None,
    cost: float | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity=f"agent-{session}", model_version="claude-x"),
        tool=ToolCall(name=tool, arguments=arguments),
        outcome=Outcome.OK,
        started_at=BASE + timedelta(minutes=minute),
        harness="claude-code",
        project=project,
        authorization=authorization,
        approval=Approval.USER,
        environment=environment,
        cost_usd=cost,
    )


def _range_args(path: str, start: int, end: int) -> dict[str, object]:
    from agentwatch.provenance import capture_ranges

    capture = capture_ranges(
        {"file_path": path, "start_line": start, "end_line": end, "new_string": "x"},
        tool_name="Edit",
    )
    return to_attribution_arguments(capture)


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        _record(
            "s1",
            "Edit",
            _range_args("/repo/app.py", 3, 5),
            minute=0,
            authorization=Authorization(source=AuthorizationSource.HUMAN_ONCE),
            environment={"vcs": {"vcs": "git", "commit": "abc1234"}},
            cost=0.25,
        )
    )
    return store


def _commit(paths: dict[str, tuple[LineRange, ...]], commit: str = "abc1234") -> CommitFacts:
    return CommitFacts(
        requested=commit,
        revision=commit,
        available=True,
        paths=tuple(paths),
        ranges=paths,
        committed_at=BASE + timedelta(minutes=5),
        message="work",
    )


def test_parse_target_kinds() -> None:
    assert parse_target("abc1234").kind == "commit"
    assert parse_target("abc1234..def5678").kind == "range"
    assert parse_target("PR123").kind == "pr"
    assert parse_target("src/app.py").kind == "file"
    assert parse_target("src/app.py:3-5").lines == (3, 5)


def test_commit_resolves_to_contributing_session_exact(tmp_path: Path) -> None:
    store = _store(tmp_path)
    git = FakeGit({"abc1234": _commit({"app.py": (LineRange(3, 5),)})})

    report = build_provenance(store, "abc1234", repo="/repo", git=git)

    assert report.no_activity is False
    assert [session.session_id for session in report.sessions] == ["s1"]
    assert report.sessions[0].harness == "claude-code"
    assert report.sessions[0].model == "claude-x"
    assert report.sessions[0].authorization == {"human-once": 1}
    assert report.sessions[0].cost_usd == 0.25
    exact = [r for r in report.ranges if r.confidence == "exact"]
    assert exact and exact[0].sessions == ("s1",)


def test_commit_with_no_session_says_no_recorded_agent_activity(tmp_path: Path) -> None:
    store = _store(tmp_path)
    git = FakeGit({"abc1234": _commit({"other.py": (LineRange(1, 2),)})})

    report = build_provenance(store, "abc1234", repo="/repo", git=git)

    assert report.no_activity is True
    assert report.status == "no recorded agent activity"
    assert "human" not in report.status.lower()
    assert "human" not in json.dumps(report.to_dict()).lower()


def test_mixed_range_when_part_of_the_commit_is_unattributed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    git = FakeGit({"abc1234": _commit({"app.py": (LineRange(1, 3),)})})

    report = build_provenance(store, "abc1234", repo="/repo", git=git)

    mixed = [r for r in report.ranges if r.confidence == "mixed"]
    assert mixed, report.to_dict()
    assert mixed[0].path.endswith("app.py")


def test_file_target_lists_sessions_without_git(tmp_path: Path) -> None:
    store = _store(tmp_path)

    report = build_provenance(store, "app.py", project="/repo")

    assert [session.session_id for session in report.sessions] == ["s1"]
    assert report.kind == "file"


def test_file_target_flags_coverage_gap_for_heuristic_only(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s2", "Write", {"file_path": "/repo/plain.py"}, minute=0))

    report = build_provenance(store, "plain.py", project="/repo")

    assert "s2" in report.coverage_gaps


def test_unavailable_git_is_not_no_activity(tmp_path: Path) -> None:
    store = _store(tmp_path)

    class NoGit:
        available = False

        def commit_facts(self, revision: str) -> CommitFacts:
            return CommitFacts(requested=revision, revision=None, available=False)

    report = build_provenance(store, "abc1234", repo="/repo", git=NoGit())

    assert report.no_activity is False
    assert "unavailable" in report.status


def test_pr_target_resolves_through_commit_message(tmp_path: Path) -> None:
    store = _store(tmp_path)
    git = FakeGit({"abc1234": _commit({"app.py": (LineRange(3, 5),)})}, prs={42: "abc1234"})

    report = build_provenance(store, "PR42", repo="/repo", git=git)

    assert report.kind == "pr"
    assert [session.session_id for session in report.sessions] == ["s1"]


# -- real-git integration: the <2 s budget ------------------------------------


def _run(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def test_commit_resolves_under_two_seconds_with_real_git(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "init", "-q")
    _run(repo, "config", "user.email", "t@example.com")
    _run(repo, "config", "user.name", "Tester")
    (repo / "app.py").write_text("one\ntwo\nthree\n", encoding="utf-8")
    _run(repo, "add", "app.py")
    _run(repo, "commit", "-q", "-m", "init")
    revision = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        _record(
            "s1",
            "Edit",
            _range_args(str(repo / "app.py"), 2, 3),
            minute=0,
            project=str(repo),
            environment={"vcs": {"vcs": "git", "commit": revision}},
        )
    )

    started = time.monotonic()
    report = build_provenance(store, revision, repo=str(repo))
    elapsed = time.monotonic() - started

    assert elapsed < 2.0
    assert report.revision == revision
    assert report.sessions  # the recorded session is credited


def test_cli_provenance_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = _store(tmp_path)
    import shutil

    shutil.copy(store.path, store_dir / "records.jsonl")

    rc = main(
        ["--set", f"store.path={store_dir}", "provenance", "app.py", "--project", "/repo", "--json"]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "file"
    assert payload["sessions"][0]["session_id"] == "s1"
