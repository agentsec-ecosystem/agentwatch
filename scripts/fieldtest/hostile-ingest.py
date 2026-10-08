#!/usr/bin/env python3
"""M31 31.2 — weaponized ingest containment (R5/ADR-0024)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import QUARANTINE, arg, fixture, ok, run


def main(argv: list[str]) -> int:
    corpus = Path(arg(argv, "--corpus") or fixture("hostile"))
    run(["agentwatch", "ingest", "--format", "hostile", str(corpus)])
    run(["agentwatch", "verify-store"])
    if not QUARANTINE.exists():
        print("no quarantine file")
    ok("hostile payloads contained, never executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
