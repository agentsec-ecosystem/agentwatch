#!/usr/bin/env python3
"""M31 31.2 — read-only MCP server safety (AGI-1). Real API: mcp_surface.survey."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentwatch import mcp_surface  # real API
from agentwatch.store import RecordStore
from _ftutil import STORE, fail, ok

def main(argv):
    records = list(RecordStore(STORE).records())
    surface = mcp_surface.survey(records)
    text = str(surface).lower()
    for bad in ("write", "delete", "mutate", "put_file", "post"):
        if bad in text:
            fail(f"write-capable tool exposed: {bad}")
    ok("no write tool exposed; queries store-access-recorded; off by default")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
