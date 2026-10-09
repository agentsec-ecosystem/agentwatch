"""Embedded rebuildable query index (M30 LUI-2, PRD 54 §LUI-2, ADR-0035).

The index is **derived**: the hash-chained JSONL store stays the sole source of
truth. Deleting the index loses nothing; every command still works (slower) and
the index rebuilds **bit-for-bit** from the chain. The index is a stdlib
``sqlite3`` artifact — no heavyweight runtime dependency (ADR-0035).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.query import search
from agentwatch.query_index import (
    INDEX_FILENAME,
    QueryIndex,
    index_path_for_store,
)
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(session: str, tool: str = "Bash", *, project: str | None = None) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=tool),
        outcome=Outcome.OK,
        started_at=START,
        project=project,
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s1", "Bash", project="proj-a"))
    store.append(_record("s2", "Read"))
    store.append(_record("s1", "Write", project="proj-a"))
    return store


def _index(store: RecordStore) -> QueryIndex:
    return QueryIndex(index_path_for_store(store.path))


def test_rebuild_is_bit_for_bit(tmp_path: Path) -> None:
    store = _store(tmp_path)
    index = _index(store)

    index.rebuild(store)
    first = index.path.read_bytes()

    index.drop()
    assert not index.exists

    index.rebuild(store)
    assert index.path.read_bytes() == first
    assert index.status().records == 3


def test_delete_index_commands_still_work(tmp_path: Path) -> None:
    store = _store(tmp_path)
    index = _index(store)

    # No index on disk: the index-backed search falls back to the chain.
    assert index.search(store, tool="Bash") == search(store, tool="Bash")
    assert not index.is_fresh(store)
    assert index.status().present is False

    # Rebuild on demand and the derived view is identical.
    index.ensure(store)
    assert index.status().present is True
    assert index.search(store, tool="Bash") == search(store, tool="Bash")


def test_indexed_search_matches_store_search(tmp_path: Path) -> None:
    store = _store(tmp_path)
    index = _index(store)
    index.rebuild(store)

    for kwargs in (
        {},
        {"tool": "Bash"},
        {"session_id": "s1"},
        {"project": "proj-a"},
        {"outcome": "ok"},
        {"tool": "Write", "session_id": "s1"},
    ):
        assert index.search(store, **kwargs) == search(store, **kwargs)  # type: ignore[arg-type]


def test_index_is_stale_after_append_and_rebuilds(tmp_path: Path) -> None:
    store = _store(tmp_path)
    index = _index(store)
    index.rebuild(store)
    assert index.is_fresh(store)

    store.append(_record("s3", "Grep"))
    assert not index.is_fresh(store)
    assert index.status().source_signature != index.compute_signature(store)

    index.rebuild(store)
    assert index.is_fresh(store)
    assert index.search(store, session_id="s3") == search(store, session_id="s3")


def test_index_is_stale_after_tombstone_and_rebuilds(tmp_path: Path) -> None:
    store = _store(tmp_path)
    index = _index(store)
    index.rebuild(store)

    store.purge_session("s1")
    # A tombstone keeps the chain hash but drops the payload, so freshness must
    # account for tombstone state, not just chain hashes.
    assert not index.is_fresh(store)

    index.rebuild(store)
    assert index.search(store, session_id="s1") == search(store, session_id="s1")


def test_corrupt_index_is_detected_and_rebuilt(tmp_path: Path) -> None:
    store = _store(tmp_path)
    index = _index(store)
    index.rebuild(store)
    index.path.write_bytes(b"not a sqlite database")

    assert not index.is_fresh(store)
    index.rebuild(store)
    assert index.search(store, session_id="s2") == search(store, session_id="s2")


def test_sessions_and_count(tmp_path: Path) -> None:
    store = _store(tmp_path)
    index = _index(store)
    index.rebuild(store)
    assert index.count() == 3
    assert sorted(index.sessions()) == ["s1", "s2"]


def test_import_does_not_pull_pyarrow(tmp_path: Path) -> None:
    """The core index ships with the CLI; parquet is a lazy optional extra (ADR-0035)."""
    code = (
        "import sys; import agentwatch.query_index; "
        "assert 'pyarrow' not in sys.modules, 'pyarrow imported eagerly'"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        env={"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
    )
    assert proc.returncode == 0, proc.stderr


def test_parquet_export_roundtrip(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    parquet = pytest.importorskip("pyarrow.parquet")
    store = _store(tmp_path)
    index = _index(store)
    index.rebuild(store)

    out = tmp_path / "export.parquet"
    count = index.export_parquet(out)
    assert count == 3

    table = parquet.read_table(out)
    assert table.num_rows == 3
    assert set(table.column_names) >= {"seq", "session_id", "tool_name", "outcome", "started_at"}
    assert "proj-a" in table.column("project").to_pylist()


def test_interactive_search_on_one_million_records(tmp_path: Path) -> None:
    """The published LUI-2 target: an indexed session lookup on 1M rows is interactive."""
    index = QueryIndex(tmp_path / "index.sqlite3")
    payload = json.dumps(_record("s-0").to_dict(), sort_keys=True, separators=(",", ":"))
    rows = (
        {
            "seq": i,
            "session_id": f"s-{i % 5000}",
            "tool_name": "Bash" if i % 3 else "Read",
            "outcome": "ok",
            "project": "proj",
            "producer_kind": "hook",
            "started_at": (START + timedelta(seconds=i)).isoformat(),
            "record": payload,
        }
        for i in range(1_000_000)
    )
    index.build_rows(rows)

    started = time.perf_counter()
    hits = index.candidates(session_id="s-1234")
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert len(hits) == 200
    # Published target: an indexed lookup on 1M records is interactive (< 250 ms).
    assert elapsed_ms < 250, f"indexed lookup took {elapsed_ms:.1f} ms"


def test_index_filename_is_stable(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert index_path_for_store(store.path).name == INDEX_FILENAME
    assert index_path_for_store(store.path).parent == store.path.parent


def test_cli_index_rebuild_status_drop(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)

    assert main(["--set", f"store.path={store_dir}", "index", "rebuild"]) == 0
    assert "fresh" in capsys.readouterr().out

    assert main(["--set", f"store.path={store_dir}", "index", "status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["fresh"] is True
    assert payload["records"] == 3

    assert main(["--set", f"store.path={store_dir}", "index", "drop"]) == 0
    capsys.readouterr()
    assert not (store_dir / INDEX_FILENAME).exists()
