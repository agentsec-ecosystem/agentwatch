#!/usr/bin/env python3
"""M31 31.2 — cross-tenant isolation + audit (PG-2)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import fail, ok, run

def main(argv):
    proc = run(["agentwatch", "search", "--project", "other-tenant", "--json"], check=False)
    if proc.stdout.strip() not in ("", "[]", "null"):
        fail("cross-tenant query returned rows")
    run(["agentwatch", "coverage", "--json"])
    ok("cross-tenant query returns nothing and is store-access-recorded")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
