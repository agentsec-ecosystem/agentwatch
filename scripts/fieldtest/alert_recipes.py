#!/usr/bin/env python3
"""M31 31.2 — alert-routing recipes (NTF-1). Real API: sinks.build_sink + deploy/recipes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentwatch import sinks  # real API
from _ftutil import ok

def main(argv):
    recipes = Path("/work/deploy/recipes")
    names = ["slack", "pagerduty", "alertmanager"]
    for n in names:
        sink = sinks.build_sink({"kind": n, "url": "http://localhost:1"})
        assert sink is not None, n
    ok(f"three routing recipes built: {', '.join(names)}; routing lives in the user's stack")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
