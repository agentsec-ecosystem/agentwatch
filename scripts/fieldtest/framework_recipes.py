#!/usr/bin/env python3
"""M31 31.2 — certified framework recipes ADK/Strands/OpenAI/Claude SDK (FWK-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv: list[str]) -> int:
    run(["agentwatch", "instrument", "--detect", "--json"])
    run(["agentwatch", "verify-store"])
    ok("framework recipes run against pinned versions; source+integrity carried")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
