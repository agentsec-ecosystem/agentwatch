#!/usr/bin/env python3
"""M31 31.2 — OCSF 1.5.0 + Syslog reference consumers (SIEM-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv: list[str]) -> int:
    run(["agentwatch", "event", "--emit", "--sink", "ocsf"])
    run(["agentwatch", "verify-store"])
    ok("OCSF/Syslog conformance green; redaction gate blocks unconfigured sinks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
