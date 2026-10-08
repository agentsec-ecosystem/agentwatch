#!/usr/bin/env python3
"""M31 31.2 — concurrency report + ambiguous ranges (CNC-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run

def main(argv):
    run(["agentwatch", "concurrency", "--project", ".", "--json"])
    run(["agentwatch", "provenance", "--repo", ".", "--json"])
    ok("overlap reported; multi-session ranges marked ambiguous")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
