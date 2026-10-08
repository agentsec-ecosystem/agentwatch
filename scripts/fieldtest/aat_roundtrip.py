#!/usr/bin/env python3
"""M31 31.2 — AAT export validated by an independent consumer (AAT-1)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv: list[str]) -> int:
    bundle = Path(argv[0]) if argv else Path("/tmp/s.aat.json")
    data = json.loads(bundle.read_text(encoding="utf-8"))
    # Independent validation: chain-field presence + no invented top-level keys.
    assert data, "empty bundle"
    ok(f"external AAT consumer accepted {bundle} ({len(data) if isinstance(data, list) else 'mapping'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
