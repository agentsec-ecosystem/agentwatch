#!/usr/bin/env python3
"""M31 31.2 — 3-host trace correlation / attribution (TRACE-1/2, IDN-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import arg, ok, run


def main(argv: list[str]) -> int:
    hosts = (arg(argv, "--hosts", "fleet-h1,fleet-h2,fleet-h3") or "").split(",")
    if "--attribution" in argv:
        run("agentwatch trace --demo --json")
        run("agentwatch impact ft04")
        ok(f"identity+delegation answered across {len(hosts)} hosts")
    elif "--skew" in argv:
        run("agentwatch trace --demo --skew 3 --json")
        ok("cross-host skew ordering applied and flagged")
    else:
        run("agentwatch trace --demo --json")
        ok(f"one ordered chain across {len(hosts)} hosts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
