"""Session export tests (M13 J2, #204)."""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.session_export import (
    EXPORT_SCHEMA,
    export_session,
    parse_ndjson,
    to_ndjson,
    verify_export,
)
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(session: str, index: int) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent-1"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=START,
        span_id=f"{session}-{index}",
        step_type=StepType.ACT,
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    for index in range(3):
        store.append(_record("s1", index))
    store.append(_record("other", 99))
    store.append(_record("s1", 3))
    return store


def test_export_selects_one_session_with_chain_segment(tmp_path: Path) -> None:
    export = export_session(_store(tmp_path), "s1")

    assert export.schema == EXPORT_SCHEMA
    assert export.count == 4
    assert all(row["record"]["session_id"] == "s1" for row in export.rows)
    assert [row["seq"] for row in export.rows] == [0, 1, 2, 4]  # 'other' skipped
    assert verify_export(export.rows)


def test_ndjson_round_trips_through_reference_consumer(tmp_path: Path) -> None:
    export = export_session(_store(tmp_path), "s1")
    text = to_ndjson(export)

    parsed = parse_ndjson(text)

    assert parsed.session_id == "s1"
    assert parsed.count == export.count
    assert verify_export(parsed.rows)


def test_verify_export_detects_tampering(tmp_path: Path) -> None:
    export = export_session(_store(tmp_path), "s1")
    rows = [dict(row) for row in export.rows]
    rows[1] = {**rows[1], "record": {**rows[1]["record"], "outcome": "error"}}

    assert not verify_export(rows)


def test_cli_exports_to_stdout_and_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main = importlib.import_module("agentwatch.cli.main")
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path))
    _store(tmp_path)
    out_file = tmp_path / "session.ndjson"

    assert main.main(["export-session", "s1", "--output", str(out_file)]) == 0
    assert out_file.exists()
    parsed = parse_ndjson(out_file.read_text(encoding="utf-8"))
    assert parsed.count == 4
    assert verify_export(parsed.rows)

    capsys.readouterr()
    assert main.main(["export-session", "s1"]) == 0
    streamed = parse_ndjson(capsys.readouterr().out)
    assert streamed.count == 4


def test_cli_reports_missing_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main = importlib.import_module("agentwatch.cli.main")
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path))
    _store(tmp_path)

    assert main.main(["export-session", "absent"]) == 1
    assert "no records" in capsys.readouterr().err


def test_export_is_deterministic(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = to_ndjson(export_session(store, "s1"))
    second = to_ndjson(export_session(store, "s1"))
    assert first == second
    # Header line is schema-stable.
    header = json.loads(first.splitlines()[0])
    assert header == {"schema": EXPORT_SCHEMA, "session_id": "s1"}
