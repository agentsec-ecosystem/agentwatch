#!/usr/bin/env python3
"""SDK-1: flush-on-exit, no-op after shutdown, at-most-once/thread-safe shutdown,
and a deterministic, thread-safe sampler.

Drives the *installed* SDK's lifecycle contract (design/sdk-lifecycle.md) with the
same assertions as packages/python-sdk/tests/test_sdk.py, run against the recorder
image's package (which ships without pytest). Real APIs only; no product logic is
re-implemented here.
"""

from __future__ import annotations

import sys
import threading
from datetime import datetime, timezone

sys.path.insert(0, "/ft/scripts")
from _ftutil import fail, ok  # noqa: E402

from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall  # noqa: E402
from agentwatch.sampling import SecurityRelevantSampler  # noqa: E402
from agentwatch.sdk import AgentWatchProvider, FlushResult  # noqa: E402


class _Rec:
    def __init__(self) -> None:
        self.flushed: list[float | None] = []
        self.shutdown_count = 0

    def flush(self, timeout: float | None = None) -> bool:
        self.flushed.append(timeout)
        return True

    def shutdown(self) -> None:
        self.shutdown_count += 1


def main(argv: list[str]) -> int:
    # 1. flush-on-exit: a normal exit flushes and shuts down exactly once.
    proc = _Rec()
    with AgentWatchProvider(processors=[proc]) as provider:
        if provider.is_shutdown:
            fail("provider reported shut down while inside the context manager")
    if not proc.flushed:
        fail("context-manager exit did not flush the processor")
    if proc.shutdown_count != 1:
        fail(f"context-manager exit shut down {proc.shutdown_count} times (want 1)")

    # 2. after shutdown, the tracer is a valid no-op that records nothing.
    after = AgentWatchProvider(processors=[_Rec()])
    after.shutdown()
    tracer = after.get_tracer("demo")
    if tracer.is_noop is not True:
        fail("tracer after shutdown is not a no-op")
    with tracer.start_as_current_span("op") as span:
        if span.is_recording():
            fail("no-op span reported recording after shutdown")

    # 3. shutdown is at-most-once and thread-safe (16 concurrent callers).
    racer = _Rec()
    racer_provider = AgentWatchProvider(processors=[racer])
    threads = [threading.Thread(target=racer_provider.shutdown) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if racer.shutdown_count != 1:
        fail(f"concurrent shutdown ran {racer.shutdown_count} times (want 1)")
    if racer_provider.is_shutdown is not True:
        fail("provider not flagged shut down after concurrent shutdown")

    # 4. flush is a bounded, non-raising result.
    result = after.flush(timeout=1.0)
    if not isinstance(result, FlushResult) or result.ok is not True:
        fail("flush did not return a successful bounded FlushResult")

    # 5. sampler determinism across replays + thread-safety.
    record = AgentRecord(
        session_id="s",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        span_id="span-1",
    )
    first = SecurityRelevantSampler().should_sample(record, ratio=0.5).value
    again = SecurityRelevantSampler().should_sample(record, ratio=0.5).value
    if first != again:
        fail("sampler is not deterministic across replays")

    decisions: list[str] = []
    lock = threading.Lock()

    def decide() -> None:
        value = SecurityRelevantSampler().should_sample(record, ratio=0.5).value
        with lock:
            decisions.append(value)

    sampler_threads = [threading.Thread(target=decide) for _ in range(32)]
    for thread in sampler_threads:
        thread.start()
    for thread in sampler_threads:
        thread.join()
    if len(set(decisions)) != 1:
        fail("sampler decisions differ across threads (not deterministic/thread-safe)")

    ok("SDK lifecycle: flush-on-exit; no-op after shutdown; at-most-once/thread-safe shutdown; deterministic sampler")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
