"""Archive segment tests (M16 S28, #243).

``archive`` seals an old chain prefix into an independently verifiable segment
and leaves one anchor. A missing segment is present-but-unavailable, never empty;
a hash disagreement is a break; replay/search read across the boundary.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.archive import (
    ARCHIVE_ANCHOR_TOOL,
    archive_anchors,
    archive_store,
    combined_records,
    load_segment,
    restore_archive,
    verify_archives,
)
from agentwatch.cli.main import main
from agentwatch.query import search
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.replay import replay_session
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith("AGENTWATCH_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path / "store"))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return tmp_path


def _record(session: str, hours: int) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=START + timedelta(hours=hours),
        harness="claude-code",
    )


def _seeded(tmp_path: Path, count: int = 4) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    for hour in range(count):
        store.append(_record("s", hour))
    return store


def test_archive_seals_prefix_and_verifies_independently(tmp_path: Path) -> None:
    store = _seeded(tmp_path)

    report = archive_store(store, store.path, before=START + timedelta(hours=2))

    assert report.archived == 2
    assert report.remaining == 2
    anchor = archive_anchors(store)[0]
    assert (anchor.first_seq, anchor.last_seq, anchor.count) == (0, 1, 2)
    assert store.verify().ok
    segment = RecordStore(report.segment_path)
    assert segment.verify().ok
    assert len(segment.records()) == 2
    live = [r for r in store.records() if r.tool.name == ARCHIVE_ANCHOR_TOOL]
    assert len(live) == 1


def test_missing_archive_is_present_but_unavailable(tmp_path: Path) -> None:
    store = _seeded(tmp_path)
    report = archive_store(store, store.path, before=START + timedelta(hours=2))
    report.segment_path.unlink()

    verdicts = verify_archives(store, tmp_path)

    assert verdicts[0].available is False
    assert verdicts[0].detail == "present-but-unavailable"
    combined = combined_records(store, tmp_path)
    assert combined.unavailable == (report.segment_id,)
    # The live records are still there; the archived range is not silently empty.
    assert len(combined.records) == 2


def test_hash_disagreement_is_a_break(tmp_path: Path) -> None:
    store = _seeded(tmp_path)
    report = archive_store(store, store.path, before=START + timedelta(hours=2))
    report.segment_path.write_bytes(report.segment_path.read_bytes() + b"\n")

    verdict = verify_archives(store, tmp_path)[0]

    assert verdict.available is True
    assert verdict.ok is False
    assert "hash disagrees" in verdict.detail


def test_combined_records_and_replay_across_boundary(tmp_path: Path) -> None:
    store = _seeded(tmp_path)
    archive_store(store, store.path, before=START + timedelta(hours=2))

    combined = combined_records(store, tmp_path)

    assert combined.unavailable == ()
    assert len(combined.records) == 4
    replayed = replay_session(store, "s", records=combined.records)
    assert [record.started_at for record in replayed] == sorted(
        record.started_at for record in replayed
    )
    assert len(replayed) == 4


def test_search_reads_across_boundary(tmp_path: Path) -> None:
    store = _seeded(tmp_path)
    archive_store(store, store.path, before=START + timedelta(hours=2))
    combined = combined_records(store, tmp_path)

    found = search(store, session_id="s", records=combined.records)

    assert len(found) == 4


def test_archive_with_nothing_older_raises(tmp_path: Path) -> None:
    store = _seeded(tmp_path)
    with pytest.raises(ValueError):
        archive_store(store, store.path, before=START - timedelta(days=1))


def test_restore_reintroduces_and_consumes_anchor(tmp_path: Path) -> None:
    store = _seeded(tmp_path)
    report = archive_store(store, store.path, before=START + timedelta(hours=2))

    restored = restore_archive(store, tmp_path, segment_id=report.segment_id)

    assert restored == 2
    assert archive_anchors(store) == []
    combined = combined_records(store, tmp_path)
    assert combined.unavailable == ()
    assert len(combined.records) == 4


def test_load_segment_ok(tmp_path: Path) -> None:
    store = _seeded(tmp_path)
    report = archive_store(store, store.path, before=START + timedelta(hours=2))
    anchor = archive_anchors(store)[0]

    segment, verdict = load_segment(tmp_path, anchor)

    assert segment is not None
    assert verdict.ok is True
    assert str(report.segment_id) == anchor.segment_id


def test_archive_rechains_checkpoints(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl", checkpoint_every=2)
    for hour in range(4):
        store.append(_record("s", hour))

    report = archive_store(store, store.path, before=START + timedelta(hours=2))

    assert report.archived >= 2
    assert store.verify().ok


def test_archive_without_a_format_marker(tmp_path: Path) -> None:
    store = _seeded(tmp_path, count=2)
    lines = store.path.read_text(encoding="utf-8").splitlines()
    store.path.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")

    report = archive_store(store, store.path, before=START + timedelta(hours=2))

    assert report.archived == 2
    assert RecordStore(report.segment_path).verify().ok


def test_rechain_handles_tombstones_and_checkpoints() -> None:
    from agentwatch.archive import _rechain
    from agentwatch.store import ChainEntry

    tombstone = ChainEntry(seq=5, prev_hash="p", hash="h", record=None, tombstone=True)
    line, digest = _rechain(3, "prev", tombstone)
    assert '"tombstone": true' in line
    assert digest

    checkpoint = ChainEntry(
        seq=6,
        prev_hash="p",
        hash="h",
        record=None,
        checkpoint=True,
        entries=5,
        at="2026-01-01T00:00:00+00:00",
    )
    line, digest = _rechain(4, "prev", checkpoint)
    assert '"checkpoint": true' in line
    assert digest


def test_restore_unknown_and_unavailable_raise(tmp_path: Path) -> None:
    store = _seeded(tmp_path)
    with pytest.raises(ValueError):
        restore_archive(store, tmp_path, segment_id="nope")

    report = archive_store(store, store.path, before=START + timedelta(hours=2))
    report.segment_path.unlink()
    with pytest.raises(ValueError):
        restore_archive(store, tmp_path, segment_id=report.segment_id)


# -- CLI ---------------------------------------------------------------------


def _cli_store(store_dir: Path, count: int = 3) -> None:
    store_dir.mkdir(parents=True, exist_ok=True)
    store = RecordStore(store_dir / "records.jsonl")
    for hour in range(count):
        store.append(_record("s", hour))


def test_cli_archive_then_verify_and_replay(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = isolated / "store"
    _cli_store(store_dir)
    before = (START + timedelta(days=1)).isoformat()

    rc = main(["--set", f"store.path={store_dir}", "archive", "--before", before])
    assert rc == 0
    assert "archived 3" in capsys.readouterr().out

    rc = main(["--set", f"store.path={store_dir}", "verify-store"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "archive" in out and "ok" in out

    rc = main(["--set", f"store.path={store_dir}", "replay", "s"])
    assert rc == 0
    assert capsys.readouterr().out.count("Bash") == 3


def test_cli_archive_reports_missing_segment(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = isolated / "store"
    _cli_store(store_dir)
    before = (START + timedelta(days=1)).isoformat()
    main(["--set", f"store.path={store_dir}", "archive", "--before", before])
    capsys.readouterr()
    for segment in (store_dir / "archives").glob("*.jsonl"):
        segment.unlink()

    rc = main(["--set", f"store.path={store_dir}", "verify-store"])

    assert rc == 0
    assert "present-but-unavailable" in capsys.readouterr().out

    rc = main(["--set", f"store.path={store_dir}", "replay", "s"])
    assert rc != 0
    err = capsys.readouterr().err
    assert "present-but-unavailable" in err
