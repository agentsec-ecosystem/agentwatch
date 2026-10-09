"""Cursor coverage reconciliation tests (M26 CUR-3, #318).

Ground truth where it exists is the committed Cursor session-tracer corpus;
Cursor records are reconciled against it, and a shortfall is classified with a
Cursor-specific cause — never left ``unexplained`` on the golden corpus.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.coverage import (
    CAUSE_CURSOR_HOOK_COVERAGE,
    CAUSE_UNEXPLAINED,
    build_coverage,
    discover_cursor_transcripts,
)
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore

TRACER = Path(__file__).resolve().parent / "testkit" / "cursor" / "cursor-session-tracer"
AT = datetime(2026, 5, 9, 14, 32, 1, tzinfo=timezone.utc)


def _cursor_record(session: str, index: int) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="cursor-agent"),
        tool=ToolCall(name="EditFile"),
        outcome=Outcome.OK,
        started_at=AT,
        span_id=f"sp-{index}",
        harness="cursor",
        step_type=StepType.ACT,
    )


def _store(tmp_path: Path, session: str, count: int) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    for index in range(count):
        store.append(_cursor_record(session, index))
    return store


def test_discovers_cursor_tracer_corpus() -> None:
    transcripts, present = discover_cursor_transcripts(TRACER)

    assert present is True
    assert set(transcripts) == {"a1b2c3d4", "dde097e6"}
    assert {t.tool_calls for t in transcripts.values()} == {6}


def test_complete_cursor_store_reconciles_cleanly(tmp_path: Path) -> None:
    store = _store(tmp_path, "a1b2c3d4", 6)

    report = build_coverage(
        store,
        transcripts=discover_cursor_transcripts(TRACER)[0],
    )

    assert report.totals["unexplained"] == 0
    session = next(s for s in report.sessions if s.session_id == "a1b2c3d4")
    assert session.capture_rate == 1.0


def test_partial_cursor_store_is_classified_not_unexplained(tmp_path: Path) -> None:
    store = _store(tmp_path, "a1b2c3d4", 2)

    report = build_coverage(
        store,
        transcripts=discover_cursor_transcripts(TRACER)[0],
    )

    session = next(s for s in report.sessions if s.session_id == "a1b2c3d4")
    causes = {gap.cause for gap in session.gaps}
    assert CAUSE_CURSOR_HOOK_COVERAGE in causes
    assert CAUSE_UNEXPLAINED not in causes
    assert report.totals["unexplained"] == 0


def test_golden_corpus_has_no_unexplained(tmp_path: Path) -> None:
    transcripts, _ = discover_cursor_transcripts(TRACER)
    store = RecordStore(tmp_path / "records.jsonl")
    for session, coverage in transcripts.items():
        for index in range(coverage.tool_calls):
            store.append(_cursor_record(session, index))

    report = build_coverage(store, transcripts=transcripts)

    assert report.totals["unexplained"] == 0
    assert report.totals["capture_rate"] == 1.0


def test_cli_coverage_cursor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    from agentwatch.cli.main import main

    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = _store(store_dir, "a1b2c3d4", 6)
    assert store.verify().ok

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "coverage",
            "--harness",
            "cursor",
            "--transcripts",
            str(TRACER),
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["totals"]["unexplained"] == 0
