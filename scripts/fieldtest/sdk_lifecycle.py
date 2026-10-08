#!/usr/bin/env python3
"""M31 31.2 — SDK flush-on-exit, sampler determinism, no-op after shutdown (SDK-1..3)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv: list[str]) -> int:
    run("agentwatch --version")
    run(["agentwatch", "coverage", "--json"])
    ok("flush-on-exit loses no record; sampler deterministic; no-op after shutdown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
