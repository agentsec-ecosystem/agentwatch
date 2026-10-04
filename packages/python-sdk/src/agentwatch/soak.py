"""Nightly soak harness (M12 K4, NFR-7 groundwork).

A bounded, deterministic soak: append many records, then assert the chain
verifies quickly, memory stays bounded, and store size grows linearly (not
explosively). Results feed ``docs/reference/resource-cost.md``.
"""

from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

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

_MB = 1024 * 1024

# Synthetic soak data is SDK-emitted (M15 S26).
SOAK_PRODUCER = Producer(kind=ProducerKind.SDK, name="agentwatch-soak")


@dataclass(frozen=True)
class SoakReport:
    """Outcome of one soak run."""

    records: int
    size_mb: float
    verify_seconds: float
    peak_mb: float
    within_bounds: bool


def _record(index: int, moment: datetime) -> AgentRecord:
    return AgentRecord(
        session_id=f"s{index % 50}",
        agent=AgentIdentity(identity="soak-agent", version="1.0"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK if index % 7 else Outcome.ERROR,
        started_at=moment,
        span_id=f"sp{index}",
        producer=SOAK_PRODUCER,
        step_type=StepType.ACT,
    )


def run_soak(
    path: Path | str,
    *,
    count: int = 5000,
    max_memory_mb: float = 256.0,
    max_verify_seconds: float = 5.0,
) -> SoakReport:
    """Append ``count`` records and report size, verify time, and peak memory."""
    store = RecordStore(path, durability="none", checkpoint_every=1000)
    moment = datetime.now(timezone.utc) - timedelta(days=30)

    tracemalloc.start()
    for index in range(count):
        store.append(_record(index, moment + timedelta(seconds=index)))
    peak = tracemalloc.get_traced_memory()[1] / _MB
    tracemalloc.stop()

    start = time.perf_counter()
    status = store.verify()
    verify_seconds = time.perf_counter() - start

    within = status.ok and peak <= max_memory_mb and verify_seconds <= max_verify_seconds
    return SoakReport(
        records=count,
        size_mb=round(store.size_bytes() / _MB, 3),
        verify_seconds=verify_seconds,
        peak_mb=round(peak, 3),
        within_bounds=within,
    )
