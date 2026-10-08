#!/usr/bin/env python3
"""M31 31.2 — AAT draft pin/drift job (AAT-5). Fails on a simulated field change."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import fail, ok, run


def main(argv: list[str]) -> int:
    run(["agentwatch", "--version"])
    # A drift job must FAIL on a simulated field change; simulate by asking for a
    # revision the pin does not match.
    proc = run("agentwatch verify-release --aat-draft simulate-drift", check=False)
    if proc.returncode == 0:
        fail("drift job did not fail on a simulated field change")
    ok("drift job fails closed on a simulated draft change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
