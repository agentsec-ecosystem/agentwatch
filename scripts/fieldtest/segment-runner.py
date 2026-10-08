#!/usr/bin/env python3
"""M31 31.2 — sealed runner segment export/import (RUN-1).

`segment export` requires an explicit runner identity and run id.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run

def main(argv):
    run(["agentwatch", "segment", "export", "--session", "ft04",
         "--runner", "ci-runner-7", "--run-id", "run-0001",
         "--out", "/tmp/segment.zip", "--json"])
    run(["agentwatch", "import-segment", "/tmp/segment.zip", "--json"])
    ok("sealed runner segment verifies and anchors")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
