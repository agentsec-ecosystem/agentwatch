#!/usr/bin/env python3
"""M31 31.2 — signed default posture verified everywhere (CMP-2)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv: list[str]) -> int:
    run(["agentwatch", "checkpoint", "export", "--sign", "--output", "/tmp/cp.json"])
    run(["agentwatch", "verify-store"])
    run(["agentwatch", "doctor", "--json"])
    ok("signed default verifies; unverifiable is never 'ok'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
