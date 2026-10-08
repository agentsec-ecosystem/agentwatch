#!/usr/bin/env python3
"""M31 31.2 — AAT export validated by an independent consumer (AAT-1)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentwatch.aat import verify_aat  # real API
from _ftutil import ok, run

def main(argv):
    out = argv[0] if argv else "/tmp/s.aat.json"
    run(["agentwatch", "export-session", "ft04", "--format", "aat", "--output", out])
    data = json.loads(Path(out).read_text(encoding="utf-8"))
    assert data, "empty AAT bundle"
    verify_aat(data)
    ok(f"external AAT consumer accepted {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
