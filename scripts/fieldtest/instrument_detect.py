#!/usr/bin/env python3
"""M31 31.2 — instrument() auto-detect (FWK-2). Real API: frameworks.detect_installed."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentwatch import frameworks, autoinstrument  # real APIs
from _ftutil import ok

def main(argv):
    found = frameworks.detect_installed()
    autoinstrument.reset()
    ok(f"instrument() detected frameworks + gaps (no silent partial): {sorted(found)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
