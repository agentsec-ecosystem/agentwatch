"""Live tail / back-fill reconciliation tests (M26 STR-2, #319).

The store is the source of truth: the stream only *notifies* (by seq). A dropped
or late notification is back-filled from the store, every gap is classified, and
a backpressured subscriber keeps ``degraded`` visible.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agentwatch.live import LiveTail
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore
from agentwatch.streaming import StreamHub

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(session: str = "s1") -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=AT,
    )


def _store(tmp_path: Path, count: int, *, session: str = "s1") -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    for _ in range(count):
        store.append(_record(session))
    return store


def test_live_tail_streams_store_records(tmp_path: Path) -> None:
    _store(tmp_path, 3)
    hub: StreamHub[int] = StreamHub(queue_size=8)
    subscriber = hub.subscribe()
    for seq in (0, 1, 2):
        hub.publish(seq)
    live = LiveTail(tmp_path / "records.jsonl", subscriber=subscriber)

    batch = live.poll()

    assert len(batch.lines) == 3
    assert batch.gaps == ()
    assert batch.degraded is False


def test_overflow_is_degraded_and_backfilled(tmp_path: Path) -> None:
    _store(tmp_path, 3)
    hub: StreamHub[int] = StreamHub(queue_size=1)
    subscriber = hub.subscribe()
    for seq in (0, 1, 2):
        hub.publish(seq)  # seq 0 is dropped by the bounded queue
    live = LiveTail(tmp_path / "records.jsonl", subscriber=subscriber)

    batch = live.poll()

    assert batch.degraded is True  # visible, not swallowed
    assert len(batch.lines) == 3  # back-filled from the store
    kinds = {gap.kind for gap in batch.gaps}
    assert "stream-drop" in kinds


def test_late_notification_backfills_from_zero(tmp_path: Path) -> None:
    _store(tmp_path, 3)
    hub: StreamHub[int] = StreamHub(queue_size=8)
    subscriber = hub.subscribe()
    hub.publish(2)  # consumer joined late; only the last seq arrived
    live = LiveTail(tmp_path / "records.jsonl", subscriber=subscriber)

    batch = live.poll()

    assert len(batch.lines) == 3


def test_purged_seq_is_classified(tmp_path: Path) -> None:
    store = _store(tmp_path, 3)
    store.append(_record("s2"))
    store.purge_session("s2")
    hub: StreamHub[int] = StreamHub(queue_size=8)
    subscriber = hub.subscribe()
    for seq in (0, 1, 2, 3):
        hub.publish(seq)
    live = LiveTail(tmp_path / "records.jsonl", subscriber=subscriber)

    batch = live.poll()

    kinds = {gap.kind for gap in batch.gaps}
    assert "purged" in kinds
    assert len(batch.lines) == 3  # the tombstoned seq is a classified gap


def test_session_filter_applies_to_backfill(tmp_path: Path) -> None:
    store = _store(tmp_path, 2, session="s1")
    store.append(_record("other"))
    hub: StreamHub[int] = StreamHub(queue_size=8)
    subscriber = hub.subscribe()
    for seq in (0, 1, 2):
        hub.publish(seq)
    live = LiveTail(tmp_path / "records.jsonl", subscriber=subscriber, session_id="s1")

    batch = live.poll()

    assert len(batch.lines) == 2
    assert all(line.record is not None and line.record.session_id == "s1" for line in batch.lines)


def test_file_mode_streams_new_records(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record())
    store.append(_record())
    live = LiveTail(path)

    first = live.poll()
    assert len(first.lines) == 2
    assert first.degraded is False

    RecordStore(path).append(_record())
    second = live.poll()
    assert len(second.lines) == 1


def test_file_mode_detects_rotation(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record())
    store.append(_record())
    live = LiveTail(path)
    live.poll()

    path.write_text("", encoding="utf-8")  # truncated/rotated away
    batch = live.poll()

    assert any(gap.kind == "rotated" for gap in batch.gaps)
    assert batch.degraded is True
