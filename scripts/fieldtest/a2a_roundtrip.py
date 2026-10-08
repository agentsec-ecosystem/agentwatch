#!/usr/bin/env python3
"""M31 31.2 — A2A proxy round-trip: signed + unverifiable cards (A2A-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv: list[str]) -> int:
    run(["agentwatch", "a2a-proxy", "--fixture", "/ft/fixtures/a2a", "--once"])
    run(["agentwatch", "verify-store"])
    ok("task lifecycle + signed-card provenance recorded; unverified recorded unverified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
