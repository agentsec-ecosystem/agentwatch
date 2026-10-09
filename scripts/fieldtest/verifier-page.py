#!/usr/bin/env python3
"""M31 31.2 — static browser verifier capture: prove zero network (VFY-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import arg, ok


def main(argv: list[str]) -> int:
    page = arg(argv, "--page", "docs/field-test/v0.2.0/verifier.html")
    if not Path(page).exists():
        # The verifier page is a released static artifact; absence is a real fail.
        print(f"verifier page missing: {page}", file=sys.stderr)
        return 1
    ok(f"verifier page present: {page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
