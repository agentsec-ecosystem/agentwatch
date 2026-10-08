#!/usr/bin/env python3
"""M31 31.2 — emit SDK spans into the unified store (PG-3, SDK)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv: list[str]) -> int:
    run(["python3", "/ft/scripts/drive-agent.py", "--session", "ft-sdk"])
    run(["agentwatch", "verify-store"])
    run(["agentwatch", "union", "--json"])
    ok("SDK spans chain-protected; union is the no-PG fallback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
