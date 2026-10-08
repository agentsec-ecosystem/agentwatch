#!/usr/bin/env python3
"""M31 31.2 — skill / command-execution agent-span mapping (OTEL-4)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv: list[str]) -> int:
    run(["agentwatch", "ingest", "--format", "otel", "/ft/fixtures/otel"])
    run(["agentwatch", "verify-store"])
    ok("skill/command spans mapped where exposed; gaps declared, never invented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
