"""Tests for ``agentwatch tail`` (M5 C2, #176; PRD 22 C2).

Read-only record stream: one line per record, most recent last, tolerating a
store written concurrently, tombstones, and malformed lines.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli import main
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore
from agentwatch.tail import Tail, follow, render_record


def _record(
    session_id: str = "sess-9f2",
    *,
    tool: str = "Bash",
    step: StepType | None = StepType.OBSERVE,
    outcome: Outcome = Outcome.OK,
    duration_ms: float | None = 42.0,
    started_at: datetime | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id=session_id,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=tool),
        outcome=outcome,
        started_at=started_at or datetime(2026, 1, 2, 14, 3, 12, tzinfo=timezone.utc),
        step_type=step,
        duration_ms=duration_ms,
    )


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path / "store"))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    for key in list(os.environ):
        if key.startswith("AGENTWATCH_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path / "store"))
    return tmp_path


def test_render_record_matches_the_documented_shape() -> None:
    line = render_record(_record())

    assert line.endswith("· sess-9f2 · observe · Bash · ok · 42ms")
    stamp = line.split(" · ")[0]
    assert stamp[:8].count(":") == 2  # HH:MM:SS
    assert stamp[8] in "+-"  # explicit UTC offset


def test_read_new_streams_records_in_order(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record(tool="Bash"))
    store.append(_record(tool="Read"))

    lines = Tail(path).read_new()

    assert [line.text.split(" · ")[3] for line in lines] == ["Bash", "Read"]
    assert all(not line.is_note for line in lines)


def test_session_filter(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record(session_id="sess-a"))
    store.append(_record(session_id="sess-b"))

    lines = Tail(path, session_id="sess-b").read_new()

    assert len(lines) == 1
    assert "sess-b" in lines[0].text


def test_tombstone_is_skipped_with_note(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(
        _record(started_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    )
    store.apply_retention(retention_days=1, now=datetime(2026, 1, 1, tzinfo=timezone.utc))

    lines = Tail(path).read_new()

    assert any(line.is_note and "tombstone" in line.text for line in lines)


def test_malformed_line_is_skipped_with_note(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    path.write_text('{"seq": 0, "nope": true}\nnot json\n', encoding="utf-8")

    lines = Tail(path).read_new()

    assert any(line.is_note for line in lines)


def test_partial_final_line_is_tolerated_until_complete(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record(tool="Bash"))
    complete = path.read_text(encoding="utf-8")
    envelope_line = complete.splitlines()[1]
    partial = envelope_line[:20]
    path.write_text(partial, encoding="utf-8")  # no trailing newline

    tail = Tail(path)
    assert tail.read_new() == []

    # The writer finishes the line in place (append), as a concurrent writer does.
    with path.open("a", encoding="utf-8") as handle:
        handle.write(envelope_line[20:] + "\n")
    lines = tail.read_new()
    assert len(lines) == 1
    assert lines[0].text.endswith("Bash · ok · 42ms")


def test_follow_picks_up_new_records(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record(tool="Bash"))
    tail = Tail(path)
    first = tail.read_new()
    assert len(first) == 1

    store.append(_record(tool="Read"))
    tailer = follow(tail, poll_seconds=0, max_polls=1, sleep=lambda _: None)
    new = list(tailer)

    assert [line.text.split(" · ")[3] for line in new] == ["Read"]


def test_absent_store_is_empty_not_an_error(tmp_path: Path) -> None:
    assert Tail(tmp_path / "missing.jsonl").read_new() == []


def test_cli_tail_prints_records(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = isolated / "store" / "records.jsonl"
    store = RecordStore(path)
    store.append(_record(tool="Bash"))

    rc = main(["tail"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "Bash" in out
    assert "observe" in out


def test_cli_tail_session_filter(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = isolated / "store" / "records.jsonl"
    store = RecordStore(path)
    store.append(_record(session_id="sess-a", tool="Bash"))
    store.append(_record(session_id="sess-b", tool="Read"))

    rc = main(["tail", "--session-id", "sess-b"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "sess-b" in out
    assert "sess-a" not in out


def test_cli_tail_json(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = isolated / "store" / "records.jsonl"
    store = RecordStore(path)
    store.append(_record(tool="Bash"))

    rc = main(["tail", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["session_id"] == "sess-9f2"
    assert payload["tool"]["name"] == "Bash"


def test_cli_tail_broken_chain_warns_but_streams(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = isolated / "store" / "records.jsonl"
    store = RecordStore(path)
    store.append(_record(tool="Bash"))
    lines = path.read_text(encoding="utf-8").splitlines()
    envelope = json.loads(lines[1])
    envelope["record"]["tool"]["name"] = "Tampered"
    lines[1] = json.dumps(envelope)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    rc = main(["tail"])

    captured = capsys.readouterr()
    assert rc == 0
    assert "chain" in captured.err.lower()
    assert "Tampered" in captured.out


def test_old_records_ordering_survives_timedelta(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record(tool="old", started_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    store.append(
        _record(
            tool="new",
            started_at=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=5),
        )
    )

    tools = [line.text.split(" · ")[3] for line in Tail(path).read_new()]
    assert tools == ["old", "new"]
