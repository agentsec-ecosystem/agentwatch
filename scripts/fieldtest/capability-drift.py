#!/usr/bin/env python3
"""M31 31.2 — capability supply chain + memory (CAP-1/2, MEM-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import arg, ok, run


def main(argv: list[str]) -> int:
    kind = arg(argv, "--kind", "drift")
    if kind == "drift":
        run(["agentwatch", "inventory", "--capabilities", "--diff"])
    elif kind == "load":
        run(["agentwatch", "replay", "ft04"])
        run(["agentwatch", "impact", "ft04"])
    else:
        run(["agentwatch", "search", "--memory"])
    ok(f"capability/memory check ({kind})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
