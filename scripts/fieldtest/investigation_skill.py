#!/usr/bin/env python3
"""M31 31.2 — investigation skill + versioned CLI JSON (AGI-2).

`evidence` takes a positional target (the session id to bundle).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run

def main(argv):
    run(["agentwatch", "evidence", "ft04", "--include", "incident-report.json", "--out", "/tmp/evidence.zip"])
    run(["agentwatch", "coverage", "--json"])
    ok("skill reaches documented answers; CLI JSON published")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
