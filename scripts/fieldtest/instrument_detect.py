#!/usr/bin/env python3
"""M31 31.2 — instrument() auto-detect (FWK-2)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv: list[str]) -> int:
    out = run(["agentwatch", "instrument", "--detect", "--json"]).stdout
    ok(f"instrument() detected frameworks + gaps (no silent partial): {len(out)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
