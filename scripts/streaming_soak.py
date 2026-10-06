#!/usr/bin/env python3
"""Streaming soak (M26 STR-3, PRD 42).

Drives the STR-1 transport + STR-2 reconciliation with a bounded, starved,
reconnecting consumer and asserts no store loss. Use ``--duration`` to pace a
large ``--count`` over a wall-clock window (the nightly job); the default is a
bounded CI run.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "python-sdk" / "src"))

from agentwatch.streaming_soak import run_streaming_soak  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="streaming soak (STR-3)")
    parser.add_argument("--count", type=int, default=50000, help="records to append")
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="spread the appends across this many seconds (0 = as fast as possible)",
    )
    parser.add_argument("--hub-size", type=int, default=8, help="bounded queue size")
    parser.add_argument("--poll-every", type=int, default=100, help="append polls per reconciliation")
    parser.add_argument(
        "--reconnect-every", type=int, default=10000, help="simulate a consumer restart every N"
    )
    args = parser.parse_args(argv)

    pace = args.duration / args.count if args.duration > 0 and args.count > 0 else 0.0
    with tempfile.TemporaryDirectory() as directory:
        report = run_streaming_soak(
            Path(directory) / "records.jsonl",
            count=args.count,
            hub_size=args.hub_size,
            poll_every=args.poll_every,
            reconnect_every=args.reconnect_every,
            pace_seconds=pace,
        )
    print(
        f"streaming-soak: {report.records} records; delivered {report.delivered}; "
        f"gaps {report.gaps}; degraded polls {report.degraded_polls}; "
        f"reconnects {report.reconnects}; size {report.size_mb} MB"
    )
    if not report.within_bounds:
        print("streaming-soak: FAILED (store loss or chain broken)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
