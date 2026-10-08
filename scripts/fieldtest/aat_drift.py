#!/usr/bin/env python3
"""M31 31.2 — AAT draft pin/drift job (AAT-5). Real API: aat.check_aat_drift."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentwatch.aat import check_aat_drift, aat_version_line  # real API
from _ftutil import fail, ok

def main(argv):
    line = aat_version_line()
    assert line, "no pinned AAT revision surfaced"
    drift = check_aat_drift({"aat_version": "draft-does-not-match", "records": []})
    if not drift:
        fail("drift job did not flag a simulated revision change")
    ok(f"pinned revision cited ({line}); drift flagged on simulated change")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
