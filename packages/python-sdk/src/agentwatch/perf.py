"""A tiny performance harness (M12 12.1, NFR-1).

Records per-call latencies and reports percentile/mean/max so NFR-1 ("≤5 ms per
step") is measured, not asserted by vibes. Pure-stdlib; used by the perf-budget
test and available to the soak job.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PerfStats:
    """Latency distribution over ``iterations`` calls, in milliseconds."""

    iterations: int
    mean_ms: float
    p50_ms: float
    p99_ms: float
    max_ms: float

    def within(self, budget_ms: float) -> bool:
        return self.p99_ms <= budget_ms


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    rank = max(0, min(len(sorted_values) - 1, int(round(percentile * (len(sorted_values) - 1)))))
    return sorted_values[rank]


def time_call(fn: Callable[[], T], *, iterations: int = 500) -> PerfStats:
    """Run ``fn`` ``iterations`` times and summarize the per-call latency (ms)."""
    if iterations < 1:
        raise ValueError("iterations must be >= 1")
    samples: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    ordered = sorted(samples)
    return PerfStats(
        iterations=iterations,
        mean_ms=statistics.fmean(samples),
        p50_ms=_percentile(ordered, 0.50),
        p99_ms=_percentile(ordered, 0.99),
        max_ms=ordered[-1],
    )
