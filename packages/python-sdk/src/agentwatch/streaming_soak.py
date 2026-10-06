"""Streaming soak harness (M26 STR-3, PRD 42).

Exercises the STR-1 transport and the STR-2 reconciliation under sustained load
with a hostile-but-deterministic consumer: it is starved (starved polls
overflow the bounded queue), it reconnects mid-run, and it must still end with
**zero store loss** — every seq reconciled from the store — and a bounded queue
with ``degraded`` surfaced.

Deterministic (no wall-clock sleeps) so it runs in CI in seconds; the scheduled
24 h job calls the same harness with a large ``count`` and pacing.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentwatch.live import LiveTail
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
from agentwatch.streaming import StreamHub

_MB = 1024 * 1024
SOAK_PRODUCER = Producer(kind=ProducerKind.SDK, name="agentwatch-stream-soak")


@dataclass(frozen=True)
class StreamingSoakReport:
    """Outcome of one streaming soak run."""

    records: int
    delivered: int
    gaps: int
    degraded_polls: int
    reconnects: int
    size_mb: float
    within_bounds: bool


def _record(index: int, moment: datetime) -> AgentRecord:
    return AgentRecord(
        session_id=f"s{index % 25}",
        agent=AgentIdentity(identity="stream-soak", version="1.0"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=moment + timedelta(seconds=index),
        span_id=f"sp{index}",
        producer=SOAK_PRODUCER,
        step_type=StepType.ACT,
    )


def run_streaming_soak(
    path: Path | str,
    *,
    count: int = 5000,
    hub_size: int = 8,
    poll_every: int = 50,
    reconnect_every: int = 0,
    pace_seconds: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
) -> StreamingSoakReport:
    """Append ``count`` records while a bounded consumer is starved/reconnected.

    ``pace_seconds`` spaces appends so a large ``count`` can span a real duration
    (the scheduled 24 h job); ``sleep`` is injectable for tests.
    """
    store = RecordStore(path, durability="none", checkpoint_every=1000)
    hub: StreamHub[int] = StreamHub(queue_size=hub_size)
    subscriber = hub.subscribe()
    live = LiveTail(path, subscriber=subscriber)
    moment = datetime.now(timezone.utc) - timedelta(days=1)

    delivered = gaps = degraded_polls = reconnects = 0
    for index in range(count):
        store.append(_record(index, moment))
        hub.publish(index)
        if reconnect_every and index and index % reconnect_every == 0:
            hub.unsubscribe(subscriber)
            subscriber = hub.subscribe()
            live.attach(subscriber)
            reconnects += 1
        if poll_every and index and index % poll_every == 0:
            batch = live.poll()
            delivered += len(batch.lines)
            gaps += len(batch.gaps)
            degraded_polls += int(batch.degraded)
        if pace_seconds:
            sleep(pace_seconds)

    final = live.poll()
    delivered += len(final.lines)
    gaps += len(final.gaps)
    degraded_polls += int(final.degraded)

    within = (
        store.verify().ok
        and delivered == count
        and count > 0
    )
    return StreamingSoakReport(
        records=count,
        delivered=delivered,
        gaps=gaps,
        degraded_polls=degraded_polls,
        reconnects=reconnects,
        size_mb=round(store.size_bytes() / _MB, 3),
        within_bounds=within,
    )


__all__ = ["SOAK_PRODUCER", "StreamingSoakReport", "run_streaming_soak"]
