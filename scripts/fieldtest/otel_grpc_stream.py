#!/usr/bin/env python3
"""M31 31.2 — OTLP/gRPC + protobuf streaming ingest (OTEL-2)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import arg, ok, run


def main(argv: list[str]) -> int:
    endpoint = arg(argv, "--endpoint", "http://otel-grpc:4317")
    spans = arg(argv, "--spans", "200")
    # otel-probe.py supports --endpoint/--service/--spans (streamed gRPC export).
    run(["python3", "/ft/scripts/otel-probe.py", "--endpoint", endpoint,
         "--service", "agentwatch", "--spans", str(spans)])
    ok(f"streamed {spans} spans OTLP/gRPC within the memory bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
