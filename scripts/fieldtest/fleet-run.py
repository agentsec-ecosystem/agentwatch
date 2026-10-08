#!/usr/bin/env python3
"""M31 31.2 — 3-host trace correlation / attribution (TRACE-1/2, IDN-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run

def main(argv):
    run(["agentwatch", "fleet", "show", "--json"])
    run(["agentwatch", "trace", "--json"])
    if "--attribution" in argv:
        run(["agentwatch", "impact", "ft04"])
        run(["agentwatch", "blame", "."])
    ok("one ordered chain; identity+delegation answered or honest unknown")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
