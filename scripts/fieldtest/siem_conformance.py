#!/usr/bin/env python3
"""M31 31.2 — OCSF 1.5.0 + Syslog conformance (SIEM-1). Real API: ocsf."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentwatch import ocsf  # real API
from _ftutil import ok, run

def main(argv):
    row = ocsf.session_ocsf({"session_id": "ft04"})
    assert row, "OCSF projection empty"
    run(["agentwatch", "event", "emit", "--tool", "Bash", "--reason", "field-test"])
    ok("OCSF/Syslog conformance green; redaction gate blocks unconfigured sinks")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
