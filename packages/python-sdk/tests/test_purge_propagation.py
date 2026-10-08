"""`purge`/retention propagate to every derived index/export (M30 EXT-5, PRD 56).

The chain stays authoritative; `purge` and retention tombstone the chain and then
propagate to the **derived** artifacts (embedded index, console view) so they
return nothing for the erased session. Known leftover artifacts (archives,
exports, repair evidence copies, quarantine) are enumerated rather than assumed
absent. Holds still fail closed.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.holds import parse_scope, record_hold_add
from agentwatch.query_index import QueryIndex, derived_artifacts, index_path_for_store
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore
from agentwatch.ui import ConsoleServer

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(session: str, tool: str = "Bash", *, when: datetime | None = None) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=tool),
        outcome=Outcome.OK,
        started_at=when or START,
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s1", "Bash"))
    store.append(_record("s2", "Read"))
    store.append(_record("s1", "Write"))
    return store


def _content(store: RecordStore, session: str) -> list[str]:
    return [
        record.tool.name
        for record in store.records()
        if record.session_id == session and record.tool.name != "session-purge"
    ]


def test_purge_propagates_to_the_index(tmp_path: Path) -> None:
    store = _store(tmp_path)
    index = QueryIndex(index_path_for_store(store.path))
    index.rebuild(store)
    assert len(index.candidates(session_id="s1")) == 2

    report = store.purge_session("s1")

    assert report.purged == 2
    # The derived index no longer holds the erased content...
    assert index.candidates(session_id="s1") == []
    # ...and a rebuild from the now-tombstoned chain only re-adds the marker.
    index.rebuild(store)
    assert [record.tool.name for record in index.candidates(session_id="s1")] == ["session-purge"]
    assert _content(store, "s1") == []


def test_console_returns_nothing_for_a_purged_session(tmp_path: Path) -> None:
    store = _store(tmp_path)
    index = QueryIndex(index_path_for_store(store.path))
    index.rebuild(store)
    store.purge_session("s1")

    with ConsoleServer(store, index=index) as server:
        import urllib.request

        request = urllib.request.Request(
            server.url + "/api/session/s1",
            headers={"X-Agentwatch-Token": server.token},
        )
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - loopback
            payload = json.loads(response.read().decode("utf-8"))
    tools = [row["record"]["tool"]["name"] for row in payload["records"]]
    assert tools == ["session-purge"]


def test_retention_propagates_to_the_index(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.append(_record("s3", "Old", when=START))
    index = QueryIndex(index_path_for_store(store.path))
    index.rebuild(store)
    assert len(index.candidates(session_id="s3")) == 1

    report = store.apply_retention(retention_days=1, now=START + timedelta(days=10))

    assert report.purged == 4
    assert index.candidates(session_id="s3") == []


def test_purge_enumerates_leftover_artifacts(tmp_path: Path) -> None:
    store = _store(tmp_path)
    (tmp_path / "archives").mkdir()
    (tmp_path / "notes.parquet").write_bytes(b"parquet")
    (tmp_path / "records.jsonl.corrupt-20260101T000000Z").write_text("x", encoding="utf-8")

    report = store.purge_session("s1")

    kinds = {entry.split(":", 1)[0] for entry in report.leftovers}
    assert {"archive", "parquet", "repair-evidence"} <= kinds


def test_derived_artifacts_lists_known_artifacts(tmp_path: Path) -> None:
    store = _store(tmp_path)
    (tmp_path / "archives").mkdir()
    (tmp_path / "export.parquet").write_bytes(b"x")
    index = QueryIndex(index_path_for_store(store.path))
    index.rebuild(store)

    found = {artifact.kind for artifact in derived_artifacts(tmp_path)}

    assert {"index", "archive", "parquet"} <= found


def test_blocked_purge_does_not_touch_the_index(tmp_path: Path) -> None:
    store = _store(tmp_path)
    hold = record_hold_add(store, parse_scope("session:s1"), reason="litigation")
    index = QueryIndex(index_path_for_store(store.path))
    index.rebuild(store)

    report = store.purge_session("s1")

    assert report.blocked_by_hold == hold.hold_id
    # Fail closed: the derived index still holds the (un-purged) content.
    tools = {record.tool.name for record in index.candidates(session_id="s1")}
    assert {"Bash", "Write"} <= tools


def test_cli_purge_propagates_and_reports_leftovers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = _store(store_dir)
    index = QueryIndex(index_path_for_store(store.path))
    index.rebuild(store)
    (store_dir / "archives").mkdir()

    rc = main(["--set", f"store.path={store_dir}", "purge", "s1", "--yes"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "purged 2" in out
    assert "leftover" in out.lower()
    assert QueryIndex(index_path_for_store(store.path)).candidates(session_id="s1") == []
    assert _content(RecordStore(store.path), "s1") == []
