#!/usr/bin/env python3
"""M31 31.2 — alert-routing recipes (NTF-1). Real API: sinks.build_sink + deploy/recipes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentwatch import sinks  # real API
from _ftutil import ok

def main(argv):
    names = ["slack", "pagerduty", "alertmanager"]
    targets = {
        "slack": "https://hooks.example.invalid/slack",
        "pagerduty": "https://events.example.invalid/pagerduty",
        "alertmanager": "syslog://localhost:514",
    }
    for n in names:
        sink = sinks.build_sink(targets[n])
        assert sink is not None, n
    ok(f"three routing recipes built: {', '.join(names)}; routing lives in the user's stack")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
