"""Session end-reason tests (M17 S33, #250)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.diff import diff_sessions
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.session_state import (
    ABANDONED,
    COMPLETED,
    ERRORED,
    INTERRUPTED,
    UNKNOWN,
    session_state,
    session_states,
)
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _boundary(session: str, *, reason: str | None, minute: int = 0) -> AgentRecord:
    arguments = {"reason": reason} if reason is not None else None
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name="session-end", arguments=arguments),
        outcome=Outcome.OK,
        started_at=START + timedelta(minutes=minute),
        step_type=None,
    )


def _tool(session: str, *, minute: int, outcome: Outcome = Outcome.OK) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name="Bash"),
        outcome=outcome,
        started_at=START + timedelta(minutes=minute),
        step_type=StepType.ACT,
    )


def test_explicit_interrupt_yields_interrupted_by_user() -> None:
    state = session_state([_tool("s1", minute=0), _boundary("s1", reason="interrupted")])
    assert state.state == INTERRUPTED
    assert state.reason == "interrupted"


def test_no_end_event_yields_abandoned() -> None:
    assert session_state([_tool("s1", minute=0)]).state == ABANDONED


def test_error_yields_errored() -> None:
    state = session_state(
        [_tool("s1", minute=0, outcome=Outcome.ERROR), _boundary("s1", reason="clear")]
    )
    assert state.state == ERRORED


def test_normal_reason_yields_completed() -> None:
    assert session_state([_boundary("s1", reason="clear")]).state == COMPLETED


def test_ambiguous_reason_yields_unknown() -> None:
    assert session_state([_boundary("s1", reason="other")]).state == UNKNOWN
    assert session_state([_boundary("s1", reason=None)]).state == UNKNOWN


def test_interrupt_beats_error() -> None:
    state = session_state(
        [_tool("s1", minute=0, outcome=Outcome.ERROR), _boundary("s1", reason="escape")]
    )
    assert state.state == INTERRUPTED


def test_session_states_reads_a_store(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_tool("s1", minute=0))
    store.append(_boundary("s1", reason="interrupted", minute=1))

    states = session_states(store, ["s1"])

    assert states["s1"].state == INTERRUPTED


def test_sessions_cli_shows_state(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    store.append(_tool("s1", minute=0))
    store.append(_boundary("s1", reason="interrupted", minute=1))

    rc = main(["--set", f"store.path={store_dir}", "sessions"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "STATE" in out
    assert INTERRUPTED in out


def test_diff_includes_states(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_tool("a", minute=0))
    store.append(_boundary("a", reason="clear", minute=1))
    store.append(_tool("b", minute=2))
    store.append(_boundary("b", reason="interrupted", minute=3))

    result = diff_sessions(store, "a", "b")

    assert result.state_a == COMPLETED
    assert result.state_b == INTERRUPTED
    assert "state: completed -> interrupted-by-user" in result.render()
