"""Tests for the terminal view and explain additions (M7 H4 / M1)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.cli import main
from agentwatch.explain import explain_session, summarize_session
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore
from agentwatch.view import list_sessions, render_session

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _record(session: str, name: str, outcome: Outcome = Outcome.OK) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=name),
        outcome=outcome,
        started_at=_T0,
    )


def test_list_sessions_and_render(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s", "Bash"))
    store.append(_record("s", "Read"))
    store.append(_record("t", "Edit"))

    assert list_sessions(store) == ["s", "t"]
    text = render_session(store, "s")
    assert "Bash" in text
    assert "Read" in text


def test_cli_view_lists_then_shows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s", "Bash"))

    assert main(["--set", f"store.path={tmp_path}", "view"]) == 0
    assert "s" in capsys.readouterr().out

    assert main(["--set", f"store.path={tmp_path}", "view", "s"]) == 0
    assert "Bash" in capsys.readouterr().out


def test_summarize_contains_the_facts(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s", "Bash"))
    store.append(_record("s", "Read", Outcome.ERROR))

    summary = summarize_session(store, "s")

    assert "records" in summary
    assert "outcomes" in summary
    assert "tools" in summary


def test_explain_defaults_to_no_narrative(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s", "Bash"))

    assert explain_session(store, "s").narrative is None


def test_explain_uses_the_narrator_when_given(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s", "Bash"))

    result = explain_session(store, "s", narrator=lambda _summary: "story")

    assert result.narrative == "story"
