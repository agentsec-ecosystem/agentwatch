"""Sizing verification tests (M12 12.3, NFR-3/5/6/7)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(index: int) -> AgentRecord:
    return AgentRecord(
        session_id=f"s{index % 10}",
        agent=AgentIdentity(identity="agent-1", version="1.0"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=START,
        span_id=f"sp{index}",
        step_type=StepType.ACT,
    )


def test_store_is_plain_utf8_jsonl(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl", durability="none")
    for index in range(50):
        store.append(_record(index))

    lines = store.path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == json.dumps({"format": 1})  # format marker
    for line in lines[1:]:
        assert isinstance(json.loads(line), dict)  # no binary/opaque framing (NFR-5)


def test_record_bytes_are_bounded(tmp_path: Path) -> None:
    count = 200
    store = RecordStore(tmp_path / "records.jsonl", durability="none")
    for index in range(count):
        store.append(_record(index))

    per_record = store.size_bytes() / count
    assert 100 < per_record < 4096, per_record


def test_default_retention_projection_stays_under_the_cap(tmp_path: Path) -> None:
    count = 200
    store = RecordStore(tmp_path / "records.jsonl", durability="none")
    for index in range(count):
        store.append(_record(index))
    per_record = store.size_bytes() / count

    # NFR-7: 10k traces/day per host for a 30-day retention window.
    projected_mb = per_record * 10_000 * 30 / (1024 * 1024)
    assert projected_mb < 1024, projected_mb  # default store.max_size_mb = 1024
