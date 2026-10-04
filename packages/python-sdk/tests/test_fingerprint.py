"""Behavior fingerprint tests (M17 S7, #249)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.fingerprint import (
    DIGEST_VERSION,
    action_sequence,
    behavior_digest,
    group_sessions_by_behavior,
    render_behavior_groups,
    session_behavior_digest,
)
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _rec(
    session: str,
    tool: str,
    *,
    step: StepType = StepType.ACT,
    outcome: Outcome = Outcome.OK,
    minute: int = 0,
    server: str | None = None,
    span: str | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=tool, server=server),
        outcome=outcome,
        started_at=START + timedelta(minutes=minute),
        step_type=step,
        span_id=span,
    )


def test_identical_sequences_share_a_digest() -> None:
    a = [_rec("s1", "Bash", span="1"), _rec("s1", "Read", step=StepType.OBSERVE, span="2")]
    b = [_rec("s2", "Bash", span="x"), _rec("s2", "Read", step=StepType.OBSERVE, span="y")]
    assert behavior_digest(a) == behavior_digest(b)


def test_added_tool_changes_digest() -> None:
    base = [_rec("s1", "Bash")]
    extra = [*base, _rec("s1", "Read")]
    assert behavior_digest(base) != behavior_digest(extra)


def test_digest_carries_its_version() -> None:
    assert behavior_digest([_rec("s1", "Bash")]).startswith(f"{DIGEST_VERSION}:")


def test_arguments_do_not_affect_the_digest() -> None:
    a = AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name="Bash", arguments={"command": "ls"}),
        outcome=Outcome.OK,
        started_at=START,
        step_type=StepType.ACT,
    )
    b = AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name="Bash", arguments={"command": "rm -rf /"}),
        outcome=Outcome.OK,
        started_at=START,
        step_type=StepType.ACT,
    )
    assert behavior_digest([a]) == behavior_digest([b])


def test_markers_are_excluded() -> None:
    record = _rec("s1", "Bash")
    marker = _rec("s1", "recorder-installed")
    assert behavior_digest([record]) == behavior_digest([marker, record])


def test_action_sequence_shape() -> None:
    sequence = action_sequence([_rec("s1", "Bash", server="mcp")])
    assert sequence == (("mcp", "bash", "act", "ok"),)


def test_group_sessions_by_behavior(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("s1", "Bash", span="1"))
    store.append(_rec("s2", "Bash", span="2"))
    store.append(_rec("s3", "Read", span="3"))

    groups = group_sessions_by_behavior(store)

    assert sorted(len(sessions) for sessions in groups.values()) == [1, 2]
    together = next(s for s in groups.values() if len(s) == 2)
    assert together == ("s1", "s2")
    assert session_behavior_digest(store, "s1") in groups
    assert "BEHAVIOR" in render_behavior_groups(groups)


def test_cli_sessions_group_by_behavior(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    store.append(_rec("s1", "Bash", span="1"))
    store.append(_rec("s2", "Bash", span="2"))

    rc = main(["--set", f"store.path={store_dir}", "sessions", "--group-by-behavior"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "bd1:" in out
    assert "s1,s2" in out
