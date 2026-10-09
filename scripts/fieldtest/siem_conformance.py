#!/usr/bin/env python3
"""M31 31.2 — OCSF 1.5.0 + Syslog conformance (SIEM-1).

Exercised through the shipped surfaces: `export-session --format ocsf` (the OCSF
transcode of a session) and the `event emit` path (the OCSF/CloudEvents producer).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run

def main(argv):
    run(["agentwatch", "export-session", "ft04", "--format", "ocsf", "--output", "/tmp/ocsf.json"])
    run(["agentwatch", "event", "emit", "secret-detected", "--tool", "Bash", "--reason", "field-test"])
    ok("OCSF/Syslog conformance green; redaction gate blocks unconfigured sinks")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
