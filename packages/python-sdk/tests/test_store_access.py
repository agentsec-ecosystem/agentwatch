"""Store-access audit tests (M15 S21, #235).

Data movements that leave the machine (or become a portable artifact) append
exactly one metadata-only ``store-access`` record; local read-only queries append
none; the chain stays green.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore
from agentwatch.store_access import (
    ACCESS_COMMANDS,
    STORE_ACCESS_TOOL,
    DestinationKind,
    record_store_access,
    store_accesses,
)

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(session: str, tool: str = "Bash") -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=tool),
        outcome=Outcome.OK,
        started_at=START,
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s1", "Bash"))
    return store


def test_record_store_access_appends_scope_and_kind(tmp_path: Path) -> None:
    store = _store(tmp_path)

    report = record_store_access(
        store,
        command="export-session",
        sessions=["s1"],
        records=4,
        destination_kind=DestinationKind.FILE,
    )

    assert report.attempted is False
    accesses = store_accesses(store)
    assert len(accesses) == 1
    access = accesses[0]
    assert access.command == "export-session"
    assert access.sessions == ("s1",)
    assert access.records == 4
    assert access.destination_kind == "file"
    assert access.attempted is False
    assert store.verify().ok


def test_failed_access_is_recorded_as_attempted(tmp_path: Path) -> None:
    store = _store(tmp_path)

    record_store_access(
        store,
        command="export-session",
        sessions=["nope"],
        records=0,
        destination_kind=DestinationKind.STDOUT,
        attempted=True,
        error="no records",
    )

    access = store_accesses(store)[0]
    assert access.attempted is True
    assert access.error == "no records"


def test_unknown_command_is_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(ValueError):
        record_store_access(store, command="search")


def test_allow_list_is_the_data_movement_commands() -> None:
    assert set(ACCESS_COMMANDS) == {
        "export",
        "export-session",
        "evidence",
        "bom",
        "quarantine-inspect",
    }


def test_cli_export_session_appends_exactly_one_access(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)
    out_file = store_dir / "session.ndjson"

    for _ in range(2):
        rc = main(
            ["--set", f"store.path={store_dir}", "export-session", "s1", "--output", str(out_file)]
        )
        assert rc == 0

    accesses = store_accesses(RecordStore(store_dir / "records.jsonl"))
    assert [a.command for a in accesses] == ["export-session", "export-session"]
    assert all(a.records == 1 for a in accesses)
    assert all(a.destination_kind == "file" for a in accesses)


def test_cli_failed_export_session_is_recorded(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)

    rc = main(["--set", f"store.path={store_dir}", "export-session", "absent"])

    assert rc != 0
    access = store_accesses(RecordStore(store_dir / "records.jsonl"))[0]
    assert access.attempted is True
    assert access.error == "no records"


def test_search_appends_no_access(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)

    rc = main(["--set", f"store.path={store_dir}", "search", "--tool", "Bash"])

    assert rc == 0
    store = RecordStore(store_dir / "records.jsonl")
    assert store_accesses(store) == []
    assert not any(r.tool.name == STORE_ACCESS_TOOL for r in store.records())
