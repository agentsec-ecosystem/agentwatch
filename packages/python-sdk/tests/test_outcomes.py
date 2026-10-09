"""OUT-1 deterministic outcome facts + `cost --per retained-change` (M30 #477, PRD 58).

Facts with numerators/denominators and a derivation version, never a quality
score. Deterministic, offline, no model in the path; unknown stays unknown.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.cost import build_cost
from agentwatch.outcomes import (
    OUTCOME_DERIVATION_VERSION,
    Ratio,
    build_outcomes,
    retained_changes,
)
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Authorization,
    AuthorizationSource,
    Outcome,
    SecurityEvent,
    ToolCall,
)
from agentwatch.store import RecordStore

START = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)


def _cmd(
    session: str,
    command: str,
    *,
    outcome: Outcome = Outcome.OK,
    minute: int = 0,
    project: str = "/repo",
    model: str = "claude-x",
    harness: str = "claude-code",
    event: SecurityEvent | None = None,
    authorization: Authorization | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity=f"agent-{session}", model_version=model),
        tool=ToolCall(name="Bash", arguments={"command": command}),
        outcome=outcome,
        started_at=START + timedelta(minutes=minute),
        harness=harness,
        project=project,
        security_event=event,
        authorization=authorization,
    )


def _file(session: str, path: str, *, minute: int = 0, project: str = "/repo") -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity=f"agent-{session}"),
        tool=ToolCall(name="Write", arguments={"file_path": path}),
        outcome=Outcome.OK,
        started_at=START + timedelta(minutes=minute),
        project=project,
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_cmd("s1", "python -m pytest tests/", minute=0))
    store.append(_cmd("s1", "mypy --strict src", outcome=Outcome.ERROR, minute=1))
    store.append(_cmd("s1", "npm run build", minute=2))
    store.append(_cmd("s2", "ls -la", minute=3))  # no test/build/lint
    store.append(
        _cmd(
            "s2",
            "cat secret",
            outcome=Outcome.DENIED,
            minute=4,
            authorization=Authorization(source=AuthorizationSource.DENIED),
        )
    )
    return store


def test_outcomes_ratios_carry_numerator_denominator_and_version(tmp_path: Path) -> None:
    store = _store(tmp_path)

    report = build_outcomes(store, by="session")

    assert report.derivation_version == OUTCOME_DERIVATION_VERSION
    row = {entry.key: entry for entry in report.rows}["s1"]
    assert row.test_pass == Ratio(1, 1)
    assert row.build_pass == Ratio(1, 1)
    assert row.lint_pass == Ratio(0, 1)
    assert row.lint_pass.value == 0.0
    assert row.rejected == 0


def test_unknown_stays_unknown_when_no_commands(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_cmd("s9", "ls -la", minute=0))

    report = build_outcomes(store, by="session")
    row = report.rows[0]

    assert row.test_pass == Ratio(0, 0)
    assert row.test_pass.value is None
    assert row.lint_pass.value is None


def test_outcomes_count_rejections_and_retries_to_success(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        _cmd(
            "s1",
            "deploy",
            outcome=Outcome.DENIED,
            minute=0,
            authorization=Authorization(source=AuthorizationSource.DENIED),
        )
    )
    store.append(_cmd("s1", "run tests", outcome=Outcome.ERROR, minute=1))
    store.append(_cmd("s1", "run tests", outcome=Outcome.OK, minute=2))

    report = build_outcomes(store, by="session")
    row = report.rows[0]

    assert row.rejected == 1
    assert row.retries_to_success == 1


def test_outcomes_by_project_model_and_harness(tmp_path: Path) -> None:
    store = _store(tmp_path)

    by_project = build_outcomes(store, by="project")
    by_model = build_outcomes(store, by="model")
    by_harness = build_outcomes(store, by="harness")

    assert {row.key for row in by_project.rows} == {"/repo"}
    assert {row.key for row in by_model.rows} == {"claude-x"}
    assert {row.key for row in by_harness.rows} == {"claude-code"}


def test_outcomes_are_deterministic_without_a_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AGENTWATCH_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    store = _store(tmp_path)

    first = build_outcomes(store, by="project").to_dict()
    second = build_outcomes(store, by="project").to_dict()

    assert first == second
    assert first["derivation_version"] == OUTCOME_DERIVATION_VERSION


# -- retained change (join to PRV-1) -----------------------------------------


def _git_repo(path: Path) -> Path:
    path.mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "t@example.com"),
        ("config", "user.name", "Tester"),
    ):
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)
    (path / "a.py").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "a.py"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-q", "-m", "init"], check=True, capture_output=True
    )
    return path


def test_retained_change_credits_a_committed_session(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "repo")
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_file("s1", str(repo / "a.py")))
    store.append(_file("s2", str(repo / "never.py")))

    # commit the change made by s1 after it happened
    (repo / "a.py").write_text("a\nb\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "a.py"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "work"], check=True, capture_output=True
    )

    result = retained_changes(store, repo=str(repo))

    assert result.known is True
    assert "s1" in result.sessions
    assert "s2" not in result.sessions
    assert result.count == 1


def test_retained_change_is_unknown_without_a_repo(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_file("s1", "/repo/a.py"))

    result = retained_changes(store, repo=None)

    assert result.known is False
    assert result.count == 0


def test_cost_per_retained_change_is_source_stamped(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "repo")
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        AgentRecord(
            session_id="s1",
            agent=AgentIdentity(identity="a", model_version="claude-3-5-sonnet"),
            tool=ToolCall(name="session-usage"),
            outcome=Outcome.OK,
            started_at=START,
            project=str(repo),
            tokens=1_000_000,
        )
    )
    store.append(_file("s1", str(repo / "a.py")))
    (repo / "a.py").write_text("a\nb\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "a.py"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "work"], check=True, capture_output=True
    )

    report = build_cost(store, per="retained-change", repo=str(repo))

    assert report.per == "retained-change"
    assert report.per_denominator == 1
    assert report.per_numerator == report.total_cost_usd
    assert report.derivation_version == OUTCOME_DERIVATION_VERSION
    payload = report.to_dict()
    assert payload["per_source"]


def test_cost_per_unknown_denominator_is_none(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        AgentRecord(
            session_id="s1",
            agent=AgentIdentity(identity="a", model_version="claude-3-5-sonnet"),
            tool=ToolCall(name="session-usage"),
            outcome=Outcome.OK,
            started_at=START,
            tokens=1_000_000,
        )
    )

    report = build_cost(store, per="retained-change", repo=None)

    assert report.per_denominator == 0
    assert report.per_value is None
    assert report.per_known is False


def test_cli_outcomes_and_cost_per_retained_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = _store(tmp_path)
    import shutil

    shutil.copy(store.path, store_dir / "records.jsonl")

    rc = main(["--set", f"store.path={store_dir}", "outcomes", "--by", "project", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["derivation_version"] == OUTCOME_DERIVATION_VERSION
    assert payload["rows"]

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "cost",
            "--per",
            "retained-change",
            "--json",
        ]
    )
    assert rc == 0
    cost_payload = json.loads(capsys.readouterr().out)
    assert cost_payload["per"] == "retained-change"
