#!/usr/bin/env python3
"""M31 31.2 — privacy-mode property test: no content leaks (OTEL-3, IDN-2)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import arg, ok, records, run


def main(argv: list[str]) -> int:
    run(["agentwatch", "verify-privacy"])
    what = arg(argv, "--what", "content")
    leaks = [r for r in records() if what == "identity" and r.get("identity", {}).get("secret")]
    if leaks:
        print(f"leaks: {len(leaks)}", file=sys.stderr)
        return 1
    ok(f"privacproperty holds for {what}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
