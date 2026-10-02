"""Tests for the append-only hash-chained JSONL store (M4 4.3/4.4)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import GENESIS_HASH, RecordStore

def _record(name: str = "Bash", session: str = "sess-1") -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=name),
        outcome=Outcome.OK,
        started_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    )


def test_append_chains_entries_and_reload_returns_records(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)

    first = store.append(_record("A"))
    second = store.append(_record("B"))

    assert first.seq == 0
    assert first.prev_hash == GENESIS_HASH
    assert second.seq == 1
    assert second.prev_hash == first.hash

    reloaded = RecordStore(path)
    assert [record.tool.name for record in reloaded.records()] == ["A", "B"]


def test_each_line_is_a_hash_chain_envelope(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record("A"))

    line = path.read_text(encoding="utf-8").splitlines()[0]
    envelope = json.loads(line)

    assert set(envelope) == {"seq", "prev_hash", "hash", "record"}
    assert envelope["record"]["tool"]["name"] == "A"


def test_size_bytes_tracks_the_file(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    assert store.size_bytes() == 0

    store.append(_record("A"))

    assert store.size_bytes() == path.stat().st_size


def test_truncated_final_line_is_surfaced_not_fatal(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record("A"))
    store.append(_record("B"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"seq": 2, "prev_hash"')

    reloaded = RecordStore(path)

    assert [record.tool.name for record in reloaded.records()] == ["A", "B"]
    assert reloaded.parse_errors == [2]


def test_verify_passes_on_a_clean_chain(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("A"))
    store.append(_record("B"))

    status = store.verify()

    assert status.ok is True
    assert status.checked == 2
    assert status.broken_at is None


def test_verify_detects_an_edited_record(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record("A"))
    store.append(_record("B"))

    lines = path.read_text(encoding="utf-8").splitlines()
    envelope = json.loads(lines[0])
    envelope["record"]["tool"]["name"] = "Tampered"
    lines[0] = json.dumps(envelope)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    status = RecordStore(path).verify()

    assert status.ok is False
    assert status.broken_at == 0


def test_verify_detects_a_deleted_middle_line(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record("A"))
    store.append(_record("B"))
    store.append(_record("C"))

    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    status = RecordStore(path).verify()

    assert status.ok is False
    assert status.broken_at == 2
