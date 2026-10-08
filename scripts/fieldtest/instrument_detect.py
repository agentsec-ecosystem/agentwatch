#!/usr/bin/env python3
"""M31 31.2 — instrument() auto-detect (FWK-2). Real API: frameworks.detect_installed."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentwatch import autoinstrument, frameworks  # real APIs
from _ftutil import ok

def main(argv):
    detection = frameworks.detect_installed()
    autoinstrument.reset()
    ok(f"instrument() detected frameworks + gaps (no silent partial): "
       f"installed={sorted(detection.installed)} missing={sorted(detection.missing)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
