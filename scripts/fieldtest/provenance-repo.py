#!/usr/bin/env python3
"""M31 31.2 — code provenance + Agent Trace export (PRV-1/2/3)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run

def main(argv):
    if "--agent-trace" in argv:
        run(["agentwatch", "export-session", "ft04", "--format", "agent-trace", "--output", "/tmp/trace.json"])
    else:
        run(["agentwatch", "provenance", "--repo", ".", "--json"])
    run(["agentwatch", "verify-store"])
    ok("provenance check")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
