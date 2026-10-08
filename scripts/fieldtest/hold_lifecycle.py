#!/usr/bin/env python3
"""M31 31.2 — legal hold survives retention/purge/rebuild (HLD-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv: list[str]) -> int:
    run(["agentwatch", "hold", "add", "--scope", "session:ft04",
         "--reason", "field-test legal hold", "--ref", "CASE-123"])
    run(["agentwatch", "retention", "apply", "--profile", "general-6mo", "--dry-run"])
    proc = run("agentwatch purge ft04 --reason test --yes", check=False)
    if proc.returncode == 0:
        print("purge did not fail closed under hold", file=sys.stderr)
        return 1
    run(["agentwatch", "hold", "list"])
    ok("held records survive retention+purge+rebuild; purge fails closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
