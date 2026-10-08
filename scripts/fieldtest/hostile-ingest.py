#!/usr/bin/env python3
"""M31 31.2 — weaponized ingest containment (R5/ADR-0024).

The shipped `agentwatch ingest` accepts a fixed format enum; malformed hostile
payloads arrive as NDJSON, so they are ingested as `ndjson` and must be
quarantined rather than executed.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import QUARANTINE, arg, fail, fixture, ok, run


def main(argv: list[str]) -> int:
    corpus = Path(arg(argv, "--corpus") or fixture("hostile"))
    run(["agentwatch", "ingest", "--format", "ndjson", str(corpus)])
    run(["agentwatch", "verify-store"])
    if not QUARANTINE.exists():
        fail("hostile payloads were not quarantined")
    ok("hostile payloads contained, never executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
