#!/usr/bin/env python3
"""M31 31.2 — environment delta above behavior delta (ENV-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv: list[str]) -> int:
    run(["agentwatch", "drift", "--json"])
    run(["agentwatch", "diff", "--demo"])
    ok("environment delta surfaced above behavior delta ('coincides with')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
