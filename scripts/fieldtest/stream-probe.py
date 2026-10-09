#!/usr/bin/env python3
"""M31 31.2 — streaming probe.

  --mode p99            STR-1: measure hook->view latency and gate p99 <= budget.
  --mode drop-consumer  STR-2: soak with a starved/reconnected consumer; assert
                        zero store loss and that gaps are classified (bounded).

Both use the real hook/socket path and the real `run_streaming_soak` API.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, "/work/packages/python-sdk/src")
from _ftutil import arg, fail, ok, records  # noqa: E402

STORE = "/data/agentwatch/records.jsonl"


def _p99(argv: list[str]) -> int:
    budget = float(arg(argv, "--budget-ms", "1000") or 1000)
    calls = int(arg(argv, "--calls", "40") or 40)
    from agentwatch.hook import build_message, default_socket_path, send

    session = "ft-str1"
    sock = default_socket_path()
    latency: list[float] = []
    for index in range(calls):
        message = build_message(
            "pre",
            {
                "session_id": session,
                "tool_name": "Bash",
                "tool_use_id": f"{session}-{index}",
                "tool_input": {"command": "ls"},
            },
        )
        started = time.perf_counter()
        send(message, socket_path=sock)
        deadline = started + 5.0
        while time.perf_counter() < deadline:
            if sum(1 for r in records() if r.get("session_id") == session) >= index + 1:
                break
            time.sleep(0.005)
        latency.append((time.perf_counter() - started) * 1000.0)
    latency.sort()
    p99 = latency[min(len(latency) - 1, int(len(latency) * 0.99))]
    visible = sum(1 for r in records() if r.get("session_id") == session)
    print(f"hook->view p50={latency[len(latency) // 2]:.1f}ms p99={p99:.1f}ms "
          f"(budget {budget:.0f}ms); {visible}/{calls} visible")
    if visible < calls:
        fail(f"only {visible}/{calls} frames became visible in the store")
    if p99 > budget:
        fail(f"hook->view p99 {p99:.1f}ms > budget {budget:.0f}ms")
    ok(f"hook->view p99 {p99:.1f}ms within the {budget:.0f}ms budget")
    return 0


def _drop_consumer(argv: list[str]) -> int:
    from agentwatch.streaming_soak import run_streaming_soak

    report = run_streaming_soak(STORE)
    # Zero store loss = every seq delivered at least once (reconnects may re-deliver).
    if report.delivered < report.records:
        fail(f"store loss on consumer crash: delivered {report.delivered} < {report.records}")
    if not report.within_bounds:
        fail(f"soak exceeded the memory/bounded-queue budget: {report}")
    ok(f"no store loss on consumer crash: {report.delivered}/{report.records} reconciled; "
       f"gaps classified={report.gaps}, reconnects={report.reconnects}, "
       f"degraded_polls={report.degraded_polls}, size={report.size_mb}MB")
    return 0


def main(argv: list[str]) -> int:
    mode = arg(argv, "--mode", "p99")
    if mode == "p99":
        return _p99(argv)
    return _drop_consumer(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
