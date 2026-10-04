"""Denied-then-retried sequence tests (M17 S25, #248)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.denials import FOLLOW_UP_N, denial_sequences, render_sequences
from agentwatch.evidence import build_bundle
from agentwatch.impact import build_impact, render_impact
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _rec(
    session: str,
    tool: str,
    *,
    minute: int,
    outcome: Outcome = Outcome.OK,
    reason: str | None = None,
) -> AgentRecord:
    event = None
    if reason is not None:
        from agentwatch.records import SecurityEvent, SecurityEventType

        event = SecurityEvent(
            type=SecurityEventType.DENIED,
            emitted_at=START + timedelta(minutes=minute),
            reason=reason,
        )
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=tool),
        outcome=outcome,
        started_at=START + timedelta(minutes=minute),
        step_type=StepType.OBSERVE,
        security_event=event,
    )


def test_denial_followed_by_different_route() -> None:
    records = [
        _rec("s1", "Bash", minute=0, outcome=Outcome.DENIED, reason="rm refused"),
        _rec("s1", "Read", minute=1),
        _rec("s1", "Write", minute=2),
    ]

    sequences = denial_sequences(records)

    assert len(sequences) == 1
    sequence = sequences[0]
    assert sequence.denied_tool == "Bash"
    assert sequence.reason == "rm refused"
    assert [f.tool for f in sequence.follow_ups] == ["Read", "Write"]
    assert sequence.empty is False
    assert "followed within" in sequence.render()


def test_denial_at_session_end_has_empty_window() -> None:
    records = [_rec("s1", "Bash", minute=0, outcome=Outcome.DENIED)]

    sequence = denial_sequences(records)[0]

    assert sequence.empty is True
    assert "no follow-up calls" in sequence.render()


def test_follow_up_window_is_bounded() -> None:
    records = [_rec("s1", "Bash", minute=0, outcome=Outcome.DENIED)]
    records.extend(_rec("s1", "Read", minute=m) for m in range(1, FOLLOW_UP_N + 5))

    sequence = denial_sequences(records)[0]

    assert len(sequence.follow_ups) == FOLLOW_UP_N


def test_multiple_denials_each_get_a_window() -> None:
    records = [
        _rec("s1", "Bash", minute=0, outcome=Outcome.DENIED),
        _rec("s1", "Read", minute=1),
        _rec("s1", "Write", minute=2, outcome=Outcome.DENIED),
        _rec("s1", "Edit", minute=3),
    ]

    assert len(denial_sequences(records)) == 2


def test_render_sequences_empty_is_blank() -> None:
    assert render_sequences(()) == ""


def test_impact_surfaces_denials(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    for record in (
        _rec("s1", "Bash", minute=0, outcome=Outcome.DENIED, reason="blocked"),
        _rec("s1", "Read", minute=1),
    ):
        store.append(record)

    report = build_impact(store, "s1")

    assert len(report.denials) == 1
    assert report.to_dict()["denials"][0]["denied_tool"] == "Bash"
    assert "denied → followed by" in render_impact(report)


def test_replay_cli_shows_sequences(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    for record in (
        _rec("s1", "Bash", minute=0, outcome=Outcome.DENIED, reason="blocked"),
        _rec("s1", "Read", minute=1),
    ):
        store.append(record)

    rc = main(["--set", f"store.path={store_dir}", "replay", "s1"])

    assert rc == 0
    assert "denied → followed by" in capsys.readouterr().out


def test_evidence_bundle_includes_denials(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("s1", "Bash", minute=0, outcome=Outcome.DENIED, reason="blocked"))
    store.append(_rec("s1", "Read", minute=1))

    bundle = build_bundle(store, store.path, "s1")

    payload = json.loads(bundle.members["denials.json"])
    assert payload["sequences"][0]["denied_tool"] == "Bash"
    assert payload["sequences"][0]["follow_ups"][0]["tool"] == "Read"
