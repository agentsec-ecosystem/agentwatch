"""Daemon->consumer streaming transport tests (M25 STR-1, #301).

Contract (design/streaming-views.md): a bounded per-subscriber queue that never
blocks the append path; overflow surfaces a visible ``degraded`` state; a dropped
consumer never loses a stored record (append-then-verify preserved).
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore
from agentwatch.streaming import StreamHub

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(i: int) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=f"tool-{i}"),
        outcome=Outcome.OK,
        started_at=AT,
    )


def test_deliveries_reach_a_subscriber_in_order() -> None:
    hub: StreamHub[str] = StreamHub(queue_size=8)
    sub = hub.subscribe()

    assert hub.publish("a") is True
    assert hub.publish("b") is True

    assert sub.get(timeout=0.1) == "a"
    assert sub.get(timeout=0.1) == "b"


def test_overflow_is_bounded_and_surfaces_degraded() -> None:
    hub: StreamHub[str] = StreamHub(queue_size=1)
    hub.subscribe()

    assert hub.publish("a") is True
    assert hub.publish("b") is False  # fills the bounded queue

    assert hub.degraded is True


def test_dropped_consumer_does_not_lose_a_stored_record(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    hub: StreamHub[str] = StreamHub(queue_size=1)
    sub = hub.subscribe()

    store.append(_record(0))  # append-then-publish: the store write happens first
    hub.publish("event-0")
    hub.publish("event-1")  # overflows the consumer
    assert hub.degraded is True

    hub.unsubscribe(sub)  # consumer disappears
    assert hub.degraded is False  # no active backpressured subscriber

    store.append(_record(1))  # the append path is unaffected

    assert store.verify().ok is True
    assert len(store.records()) == 2


def test_publish_is_safe_with_no_subscribers() -> None:
    hub: StreamHub[str] = StreamHub()
    assert hub.publish("nobody-listening") is True
    assert hub.degraded is False


def test_concurrent_publish_never_raises() -> None:
    hub: StreamHub[int] = StreamHub(queue_size=4)
    hub.subscribe()

    errors: list[BaseException] = []

    def worker() -> None:
        try:
            for i in range(100):
                hub.publish(i)
        except BaseException as exc:  # noqa: BLE001 - the test asserts none happen
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []


def test_degraded_clears_when_a_healthy_subscriber_remains() -> None:
    hub: StreamHub[str] = StreamHub(queue_size=1)
    slow = hub.subscribe()
    fast = hub.subscribe()
    hub.publish("a")
    hub.publish("b")  # both queues full

    fast.get(timeout=0.1)
    fast.get(timeout=0.1)

    assert hub.degraded is True  # `slow` is still backpressured
    hub.unsubscribe(slow)
    assert hub.degraded is False