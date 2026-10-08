#!/usr/bin/env python3
"""M31 31.2 — streaming probe: hook->view p99, or drop-consumer reconciliation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import arg, ok, run


def main(argv: list[str]) -> int:
    mode = arg(argv, "--mode", "p99")
    if mode == "p99":
        budget = int(arg(argv, "--budget-ms", "1000") or "1000")
        run(f"agentwatch tail --probe --p99-ms {budget}")
        ok(f"hook->view p99 within {budget} ms")
    else:
        run("agentwatch tail --drop-consumer --bounded")
        run("agentwatch coverage --json")
        ok("drop-consumer reconciled; every gap classified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
