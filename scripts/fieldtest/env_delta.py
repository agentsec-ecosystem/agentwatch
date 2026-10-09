#!/usr/bin/env python3
"""M31 31.2 — environment delta above behavior delta (ENV-1).

`agentwatch diff` is a behavioural diff of two *sessions*, so seed the
deterministic fixtures first, then diff two of the seeded sessions.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv):
    run(["python3", "/ft/scripts/seed-fixtures.py", "--store", "/data/agentwatch/records.jsonl"])
    run(["agentwatch", "drift", "--json"])
    run(["agentwatch", "diff", "ft-seed-mcp-a", "ft-seed-mcp-b", "--json"])
    run(["agentwatch", "sessions", "--group-by-env"])
    ok("environment delta surfaced above behavior delta ('coincides with')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
