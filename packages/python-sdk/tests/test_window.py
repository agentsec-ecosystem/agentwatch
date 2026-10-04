"""`agentwatch at` tests (M17 S24, #247)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.recorder_state import close_coverage_window, open_coverage_window
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore
from agentwatch.window import build_window, parse_duration, parse_moment, render_window

BASE = datetime(2026, 1, 2, 3, 0, 0, tzinfo=timezone.utc)


def _rec(session: str, tool: str, *, minute: int, project: str = "/repo") -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity=f"a-{session}"),
        tool=ToolCall(name=tool),
        outcome=Outcome.OK,
        started_at=BASE + timedelta(minutes=minute),
        project=project,
        step_type=StepType.ACT,
    )


MOMENT = "2026-01-02T03:00:00+00:00"


def test_window_is_time_ordered_across_sessions(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("s2", "Read", minute=10))
    store.append(_rec("s1", "Bash", minute=5))
    store.append(_rec("s3", "Edit", minute=45))

    report = build_window(store, MOMENT, window="30m")

    assert [r.session_id for r in report.records] == ["s1", "s2"]
    assert report.sessions == ("s1", "s2")


def test_window_states_a_gap(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("s1", "Bash", minute=5))
    gap = _rec("s1", "recording-gap", minute=6)
    store.append(gap)

    report = build_window(store, MOMENT, window="30m")

    assert report.gap is True
    assert report.gap_reason is not None and "recording-gap" in report.gap_reason


def test_window_covered_by_coverage_record(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    open_coverage_window(store, now=BASE - timedelta(hours=1))
    close_coverage_window(store, now=BASE + timedelta(hours=1))

    report = build_window(store, MOMENT, window="30m")

    assert report.gap is False


def test_empty_window_notes_that_recording_was_active(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    open_coverage_window(store, now=BASE - timedelta(hours=1))
    close_coverage_window(store, now=BASE + timedelta(hours=1))

    report = build_window(store, MOMENT, window="30m")

    assert report.records == ()
    assert report.note is not None and "nothing happened" in report.note


def test_no_coverage_data_is_distinguished(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")

    report = build_window(store, MOMENT, window="30m")

    assert report.gap is None
    assert report.note is not None and "nothing recorded" in report.note
    assert "resolved UTC range" in render_window(report)


def test_offset_input_is_echoed_as_utc() -> None:
    moment = parse_moment("2026-01-02 14:00+02:00")
    assert moment == datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)


def test_naive_input_uses_local_tz() -> None:
    moment = parse_moment("2026-01-02 14:00", local_tz=timezone.utc)
    assert moment == datetime(2026, 1, 2, 14, 0, tzinfo=timezone.utc)


def test_parse_duration_and_invalid() -> None:
    assert parse_duration("30m") == timedelta(minutes=30)
    assert parse_duration("2d") == timedelta(days=2)
    with pytest.raises(ValueError):
        parse_duration("soon")


def test_cli_at_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    store.append(_rec("s1", "Bash", minute=5))
    store.append(_rec("s2", "Read", minute=10))

    rc = main(["--set", f"store.path={store_dir}", "at", MOMENT, "--window", "30m", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["sessions"] == ["s1", "s2"]
    assert payload["start_utc"] == "2026-01-02T03:00:00+00:00"


def test_cli_at_bad_window(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    RecordStore(store_dir / "records.jsonl")
    rc = main(["--set", f"store.path={store_dir}", "at", MOMENT, "--window", "soon"])
    assert rc != 0
    assert "invalid duration" in capsys.readouterr().err
