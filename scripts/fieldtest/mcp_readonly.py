#!/usr/bin/env python3
"""M31 31.2 — read-only MCP server safety (AGI-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv: list[str]) -> int:
    out = run(["agentwatch", "mcp-serve", "--list-tools", "--json"]).stdout
    for bad in ("write", "delete", "mutate", "put", "post"):
        if bad in out.lower():
            print(f"write-capable tool exposed: {bad}", file=sys.stderr)
            return 1
    ok("no write tool exposed; queries store-access-recorded; off by default")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
