#!/usr/bin/env python3
"""Long-session / soak generator (M23 FT-06).

Emits N tool-call pairs through the real hook/socket path inside the recorder and
reports send-latency percentiles. Bounded and finite so it can run in CI.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time

sys.path.insert(0, "/work/packages/python-sdk/src")
from agentwatch.hook import build_message, default_socket_path, send  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--session", default="ft-soak")
    parser.add_argument("--socket", default=None)
    parser.add_argument(
        "--min-delivery",
        type=float,
        default=1.0,
        help="minimum fraction of calls that must be delivered to pass (1.0 = all)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.0,
        help="seconds to sleep between calls (0 = burst; realistic cadence avoids backlog drops)",
    )
    args = parser.parse_args(argv)

    socket_path = args.socket or default_socket_path()
    latencies: list[float] = []
    delivered = 0
    for index in range(args.count):
        call = f"soak-{index}"
        event = {"session_id": args.session, "tool_name": "Bash", "tool_use_id": call}
        start = time.perf_counter()
        ok_pre = send(build_message("pre", {**event, "tool_input": {"command": "ls"}}), socket_path=socket_path)
        ok_post = send(build_message("post", {**event, "duration_ms": 1}), socket_path=socket_path)
        latencies.append(time.perf_counter() - start)
        if ok_pre and ok_post:
            delivered += 1
        if args.interval > 0:
            time.sleep(args.interval)

    ordered = sorted(latencies)
    p50 = ordered[len(ordered) // 2]
    p99 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.99))]
    print(
        f"run-soak: {delivered}/{args.count} calls delivered; "
        f"p50={p50 * 1000:.2f}ms p99={p99 * 1000:.2f}ms "
        f"mean={statistics.fmean(latencies) * 1000:.2f}ms"
    )
    return 0 if delivered >= args.count * args.min_delivery else 1


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
