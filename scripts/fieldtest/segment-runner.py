#!/usr/bin/env python3
"""M31 31.2 — sealed runner segment export/import (RUN-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run

def main(argv):
    run(["agentwatch", "segment", "export", "--session", "ft04", "--out", "/tmp/segment.tar", "--json"])
    run(["agentwatch", "import-segment", "/tmp/segment.tar", "--json"])
    ok("sealed runner segment verifies and anchors")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
