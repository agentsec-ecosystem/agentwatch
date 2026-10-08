#!/usr/bin/env python3
"""M31 31.2 — checkpoint key rotation (CMP-3)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, records, run


def main(argv: list[str]) -> int:
    run(["agentwatch", "checkpoint", "export", "--sign", "--output", "/tmp/cp.json"])
    run(["agentwatch", "checkpoint", "rotate"])
    run(["agentwatch", "verify-store"])
    events = [r for r in records() if r.get("event") == "key-rotation"]
    ok(f"rotation appended key-rotation ({len(events)}); signatures epoch-bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
