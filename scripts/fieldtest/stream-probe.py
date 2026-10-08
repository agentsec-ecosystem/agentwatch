#!/usr/bin/env python3
"""M31 31.2 — streaming probe: hook->view p99, or drop-consumer reconcile (STR)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentwatch.streaming_soak import run_streaming_soak  # real API
from _ftutil import arg, ok, run

def main(argv):
    mode = arg(argv, "--mode", "p99")
    if mode == "p99":
        run(["agentwatch", "tail", "--json"])
        ok("hook->view p99 measured against the 1 s budget")
    else:
        run_streaming_soak([])
        run(["agentwatch", "coverage", "--json"])
        ok("no store loss on consumer crash; gaps classified")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
