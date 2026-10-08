#!/usr/bin/env python3
"""M31 31.2 — authorization/oversight corpus (APV-1/2/3, SBX-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentwatch import oversight  # real API
from _ftutil import ok, run

def main(argv):
    if "--modes" in argv:
        run(["agentwatch", "coverage", "--json"])
    run(["agentwatch", "oversight", "--json"])
    if "--sandbox" in argv:
        oversight.sandbox_boundary_event({"tool": "Bash"})
    ok("oversight check")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
