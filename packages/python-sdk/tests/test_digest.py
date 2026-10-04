"""`agentwatch digest` tests (M17 S37, #251)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.digest import build_digest, render_digest
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore

NOW = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)


def _rec(
    session: str,
    tool: str,
    *,
    days_ago: float,
    outcome: Outcome = Outcome.OK,
    tokens: int | None = None,
    model: str | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a", model_version=model),
        tool=ToolCall(name=tool),
        outcome=outcome,
        started_at=NOW - timedelta(days=days_ago),
        tokens=tokens,
        step_type=StepType.OBSERVE,
        project="/repo",
    )


def _seeded(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("s1", "Bash", days_ago=2))
    store.append(
        _rec("s1", "session-usage", days_ago=2, tokens=1_000_000, model="claude-3-5-sonnet")
    )
    store.append(_rec("s1", "Bash", days_ago=1, outcome=Outcome.DENIED))
    store.append(_rec("s1", "recording-gap", days_ago=0.5))
    return store


def test_digest_names_sessions_cost_and_gaps(tmp_path: Path) -> None:
    report = build_digest(_seeded(tmp_path), since="7d", now=NOW)

    markdown = render_digest(report)
    assert "s1" in markdown
    assert "15.0000" in markdown
    assert "recording-gap record" in markdown
    assert report.gaps == 1
    assert report.denials == 1
    assert report.total_cost_usd == 15.0


def test_digest_empty_window_is_explicit(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    report = build_digest(store, since="7d", now=NOW)
    assert report.empty is True
    assert "No agent activity recorded" in render_digest(report)


def test_digest_is_read_only(tmp_path: Path) -> None:
    store = _seeded(tmp_path)
    before = store.path.read_bytes()

    build_digest(store, since="7d", now=NOW)

    assert store.path.read_bytes() == before


def test_digest_states_stopped_recording(tmp_path: Path) -> None:
    store = _seeded(tmp_path)
    from agentwatch.recorder_state import close_coverage_window, open_coverage_window

    open_coverage_window(store, now=NOW - timedelta(days=3))
    close_coverage_window(store, now=NOW - timedelta(days=1))

    report = build_digest(store, since="7d", now=NOW)

    assert report.coverage_active is False
    assert "stopped" in render_digest(report)


def test_cli_digest_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    now = datetime.now(timezone.utc)
    store.append(
        AgentRecord(
            session_id="s1",
            agent=AgentIdentity(identity="a"),
            tool=ToolCall(name="Bash"),
            outcome=Outcome.OK,
            started_at=now - timedelta(days=1),
            project="/repo",
            step_type=StepType.ACT,
        )
    )

    rc = main(["--set", f"store.path={store_dir}", "digest", "--since", "7d"])

    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("# agentwatch digest")
    assert "s1" in out
    assert "nothing was sent anywhere" in out
