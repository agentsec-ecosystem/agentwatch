"""Tests for search, diff, and tail alerts (M8 additions H2/H3/H5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli import main
from agentwatch.diff import diff_sessions
from agentwatch.query import search, since_cutoff
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    SecurityEvent,
    SecurityEventType,
    ToolCall,
)
from agentwatch.store import RecordStore

_NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _record(
    session: str,
    name: str,
    *,
    outcome: Outcome = Outcome.OK,
    started_at: datetime = _NOW,
    security_event: SecurityEvent | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=name),
        outcome=outcome,
        started_at=started_at,
        security_event=security_event,
    )


def test_search_filters_by_tool_outcome_and_session(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s", "Bash"))
    store.append(_record("s", "Read", outcome=Outcome.ERROR))
    store.append(_record("t", "Bash"))

    assert [r.tool.name for r in search(store)] == ["Bash", "Read", "Bash"]
    assert [r.session_id for r in search(store, session_id="s")] == ["s", "s"]
    assert [r.tool.name for r in search(store, tool="Bash")] == ["Bash", "Bash"]
    assert [r.tool.name for r in search(store, outcome="error")] == ["Read"]


def test_search_since_excludes_old_records(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    now = datetime.now(timezone.utc)
    store.append(_record("s", "Old", started_at=now - timedelta(days=3)))
    store.append(_record("s", "New", started_at=now - timedelta(hours=1)))

    records = search(store, since="2d")

    assert [r.tool.name for r in records] == ["New"]


def test_since_cutoff_accepts_iso() -> None:
    cutoff = since_cutoff("2026-01-01T00:00:00+00:00")
    assert cutoff == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_cli_search_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s", "Bash"))

    assert main(["--set", f"store.path={tmp_path}", "search", "--tool", "Bash", "--json"]) == 0
    out = capsys.readouterr().out
    assert '"name": "Bash"' in out


def test_diff_reports_added_and_removed_tools(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("a", "Read"))
    store.append(_record("a", "Read"))
    store.append(_record("b", "Read"))
    store.append(_record("b", "Write"))
    store.append(_record("b", "Write"))

    result = diff_sessions(store, "a", "b")

    assert result.records_a == 2
    assert result.records_b == 3
    assert result.added_tools == ("Write",)
    assert result.removed_tools == ()


def test_diff_counts_failures(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("a", "Read"))
    store.append(_record("b", "Read", outcome=Outcome.ERROR))

    result = diff_sessions(store, "a", "b")

    assert result.failed_a == 0
    assert result.failed_b == 1


def test_cli_diff_renders(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("a", "Read"))
    store.append(_record("b", "Write"))

    assert main(["--set", f"store.path={tmp_path}", "diff", "a", "b"]) == 0
    out = capsys.readouterr().out
    assert "diff a -> b" in out
    assert "added tools: Write" in out


def test_cli_tail_alert_marks_security_signals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    event = SecurityEvent(
        type=SecurityEventType.SECRET_DETECTED,
        emitted_at=_NOW,
        emitter="claude-code",
        tool="Bash",
    )
    store.append(_record("s", "Bash", security_event=event))

    assert main(["--set", f"store.path={tmp_path}", "tail", "--alert"]) == 0
    out = capsys.readouterr().out
    assert "ALERT" in out
    assert "Bash" in out


def test_cli_tail_without_alert_has_no_prefix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    event = SecurityEvent(
        type=SecurityEventType.SECRET_DETECTED,
        emitted_at=_NOW,
        emitter="claude-code",
        tool="Bash",
    )
    store.append(_record("s", "Bash", security_event=event))

    assert main(["--set", f"store.path={tmp_path}", "tail"]) == 0
    assert "ALERT" not in capsys.readouterr().out
