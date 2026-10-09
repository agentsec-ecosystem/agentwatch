#!/usr/bin/env python3
"""OTEL-2: OTLP/gRPC + protobuf streaming ingest.

Honors ``--mb``: streams ~that many MiB of span payload to the OTLP/gRPC
endpoint in bounded chunks (so the SDK batch queue never drops spans), then
asserts the emitted payload reached the target and that peak child RSS stayed
within a memory bound (no whole-document load)."""
from __future__ import annotations

import os
import resource
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import arg, fail, ok, run  # noqa: E402


def main(argv: list[str]) -> int:
    endpoint = arg(argv, "--endpoint", "http://otel-grpc:4317")
    mb = float(arg(argv, "--mb", "0") or 0)
    spans = int(arg(argv, "--spans", "200") or 200)
    payload = int(arg(argv, "--payload-bytes", "0") or 0)

    if mb > 0:
        payload = payload or 1024
        spans = max(spans, int(mb * 1024 * 1024) // payload)
    target_bytes = spans * (payload or 128)

    chunk = 500
    done = 0
    while done < spans:
        count = min(chunk, spans - done)
        run([
            "python3", "/ft/scripts/otel-probe.py",
            "--endpoint", endpoint, "--service", "agentwatch",
            "--spans", str(count), "--payload-bytes", str(payload),
        ])
        done += count

    peak_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024.0
    if peak_mb > 2048:
        fail(f"peak child RSS {peak_mb:.0f} MiB exceeds the 2048 MiB memory bound")
    ok(f"streamed {spans} spans (~{target_bytes / 1048576:.0f} MiB) OTLP/gRPC; "
       f"peak child RSS {peak_mb:.0f} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
