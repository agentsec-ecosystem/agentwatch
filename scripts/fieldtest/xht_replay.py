#!/usr/bin/env python3
"""M31 31.2 — cross-harness test-kit replay / self-test / cross-parser (XHT)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentwatch import conformance  # real API
from _ftutil import ok

def main(argv):
    names = conformance.registered_names()
    assert names, "no adapters registered"
    results = conformance.run()
    if "--self-test" in argv:
        assert results, "replay produced no results"
    ok(f"xht replay across {len(names)} adapters; broken adapter fails")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
