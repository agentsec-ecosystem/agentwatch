#!/usr/bin/env python3
"""M31 31.2 — role x data-class matrix + access log (ACC-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run

def main(argv):
    if "--roles" in argv:
        run(["agentwatch", "access", "matrix", "--json"])
    else:
        run(["agentwatch", "access", "log", "--json"])
    ok("role matrix / access log")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
