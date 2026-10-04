"""Read-time SDK/hook union tests (M21 S11, #268)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    Producer,
    ProducerKind,
    StepType,
    ToolCall,
)
from agentwatch.store import RecordStore
from agentwatch.union import SOURCE_HOOK, SOURCE_SDK, render_union, source_of, union

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(producer: Producer, *, session: str = "s1", tool: str = "Bash") -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=tool),
        outcome=Outcome.OK,
        started_at=AT,
        producer=producer,
        step_type=StepType.ACT,
    )


HOOK = _record(Producer(kind=ProducerKind.HOOK, name="claude-code"))
SDK = _record(Producer(kind=ProducerKind.SDK, name="agentwatch"), tool="run")


def test_source_of_maps_producer_kind() -> None:
    assert source_of(HOOK) == SOURCE_HOOK
    assert source_of(SDK) == SOURCE_SDK


def test_union_returns_both_sources_with_source_set(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(HOOK)
    store.append(SDK)

    rows = union(store)

    assert [row.source for row in rows] == [SOURCE_HOOK, SOURCE_SDK]
    assert rows[0].chain_protected is True
    assert rows[1].chain_protected is False


def test_union_filters_by_source(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(HOOK)
    store.append(SDK)

    rows = union(store, source=SOURCE_SDK)

    assert len(rows) == 1
    assert rows[0].source == SOURCE_SDK


def test_render_labels_sdk_as_not_chain_protected() -> None:
    from agentwatch.union import union_records

    text = render_union(union_records([SDK]))

    assert "NOT chain-protected" in text
    assert "read-only" in text


def test_cli_union_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    store.append(HOOK)
    store.append(SDK)

    rc = main(["--set", f"store.path={store_dir}", "union", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert {row["source"] for row in payload} == {"hook", "sdk"}
    sdk_row = next(row for row in payload if row["source"] == "sdk")
    assert sdk_row["chain_protected"] is False
