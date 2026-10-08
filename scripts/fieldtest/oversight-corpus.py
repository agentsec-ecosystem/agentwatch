#!/usr/bin/env python3
"""M31 31.2 — authorization/oversight corpus (APV-1/2/3, SBX-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv: list[str]) -> int:
    if "--fidelity" in argv:
        run(["agentwatch", "oversight", "--json"])
    elif "--modes" in argv:
        run(["agentwatch", "search", "--mode", "bypass"])
    elif "--sandbox" in argv:
        run(["agentwatch", "oversight", "--sandbox", "--json"])
    else:
        run(["agentwatch", "oversight", "--since", "30d", "--json"])
    ok("oversight check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
