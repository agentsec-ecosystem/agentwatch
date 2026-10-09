"""Agent memory-surface records + `search --memory` (M28 DET-7, #357; PRD 43 §DET-7).

Memory reads/writes/deletes become observable records (the inherited "no
memory-audit" gap, G9): metadata (operation + key) is always recorded; the
memory *content* is captured only when the privacy mode and the per-field
``capture_memory`` flag allow it. `search --memory` filters them.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.memory import (
    MEMORY_TOOL,
    MemoryError,
    is_memory_record,
    memory_events,
    record_memory,
)
from agentwatch.query import search
from agentwatch.records import RecordPrivacyMode
from agentwatch.redact import PrivacyMode, RedactionConfig
from agentwatch.store import RecordStore

AT = datetime(2026, 10, 6, 12, 0, 0, tzinfo=timezone.utc)


def _store(tmp_path: Path) -> RecordStore:
    return RecordStore(tmp_path / "records.jsonl")


# --------------------------------------------------------------------------- record


def test_write_read_delete_are_recorded(tmp_path: Path) -> None:
    store = _store(tmp_path)

    record_memory(store, "s1", "write", key="prefs", now=AT)
    record_memory(store, "s1", "read", key="prefs", now=AT)
    record_memory(store, "s1", "delete", key="prefs", now=AT)

    events = memory_events(store, session_id="s1")
    assert [event.operation for event in events] == ["write", "read", "delete"]
    assert {event.key for event in events} == {"prefs"}


def test_unknown_operation_fails_loudly(tmp_path: Path) -> None:
    store = _store(tmp_path)

    with pytest.raises(MemoryError, match="unknown memory operation"):
        record_memory(store, "s1", "peek", key="prefs")


def test_metadata_is_always_recorded_and_content_is_not(tmp_path: Path) -> None:
    store = _store(tmp_path)
    redaction = RedactionConfig(mode=PrivacyMode.METADATA_ONLY, capture_memory=True)

    record_memory(
        store, "s1", "write", key="prefs", content="secret-value", redaction=redaction, now=AT
    )

    record = store.records()[0]
    assert record.tool.name == MEMORY_TOOL
    assert record.tool.privacy_mode == RecordPrivacyMode.METADATA_ONLY
    assert record.tool.arguments is not None
    assert record.tool.arguments["operation"] == "write"
    assert record.tool.arguments["key"] == "prefs"
    assert "content" not in record.tool.arguments


def test_content_is_captured_only_when_the_field_is_enabled(tmp_path: Path) -> None:
    store = _store(tmp_path)
    redaction = RedactionConfig(mode=PrivacyMode.FULL, capture_memory=True)

    record_memory(store, "s1", "write", key="prefs", content="hello", redaction=redaction, now=AT)

    event = memory_events(store, session_id="s1")[0]
    assert event.content == "hello"
    assert event.content_captured is True


def test_content_stays_out_when_capture_memory_is_off(tmp_path: Path) -> None:
    store = _store(tmp_path)
    redaction = RedactionConfig(mode=PrivacyMode.FULL, capture_memory=False)

    record_memory(store, "s1", "write", key="prefs", content="hello", redaction=redaction, now=AT)

    assert memory_events(store, session_id="s1")[0].content is None


# --------------------------------------------------------------------------- search


def test_is_memory_record() -> None:
    from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall

    memory = AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=MEMORY_TOOL),
        outcome=Outcome.OK,
        started_at=AT,
    )
    other = AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=AT,
    )

    assert is_memory_record(memory) is True
    assert is_memory_record(other) is False


def test_search_memory_only_returns_memory_records(tmp_path: Path) -> None:
    store = _store(tmp_path)
    from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall

    store.append(
        AgentRecord(
            session_id="s1",
            agent=AgentIdentity(identity="a"),
            tool=ToolCall(name="Bash"),
            outcome=Outcome.OK,
            started_at=AT,
        )
    )
    record_memory(store, "s1", "write", key="prefs", now=AT)

    records = search(store, memory_only=True)

    assert [record.tool.name for record in records] == [MEMORY_TOOL]


def test_cli_search_memory(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = _store(store_dir)
    record_memory(store, "s1", "write", key="prefs", now=AT)
    from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall

    store.append(
        AgentRecord(
            session_id="s1",
            agent=AgentIdentity(identity="a"),
            tool=ToolCall(name="Bash"),
            outcome=Outcome.OK,
            started_at=AT,
        )
    )

    rc = main(["--set", f"store.path={store_dir}", "search", "--memory", "--json"])

    assert rc == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert [row["tool"]["name"] for row in lines] == [MEMORY_TOOL]


def test_g9_memory_surfaces_are_observable(tmp_path: Path) -> None:
    # The inherited G9 gap ("no memory-audit") is closed with a proving test:
    # every memory read/write/delete is an observable, searchable record.
    store = _store(tmp_path)

    record_memory(store, "s1", "write", key="k", now=AT)
    record_memory(store, "s1", "read", key="k", now=AT)
    record_memory(store, "s1", "delete", key="k", now=AT)

    observed = {event.operation for event in memory_events(store)}
    assert observed == {"read", "write", "delete"}
    assert len(search(store, memory_only=True)) == 3
