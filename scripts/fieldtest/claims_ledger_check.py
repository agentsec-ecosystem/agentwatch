#!/usr/bin/env python3
"""CLAIM-1: the claims ledger is complete — every claim is backed and the
generated table + known-limitations are present (was `json.tool` only)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from _ftutil import fail, ok  # noqa: E402

REPO = Path("/work") if Path("/work/docs").exists() else Path(__file__).resolve().parents[2]
LEDGER = REPO / "docs/release/claims-ledger.json"


def main(argv: list[str]) -> int:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    if not ledger.get("schema"):
        fail("claims ledger has no schema field")
    claims = ledger.get("claims") or []
    if not claims:
        fail("claims ledger has no claims")
    missing = [
        c.get("id", "?")
        for c in claims
        if not (c.get("claim") and c.get("source") and c.get("evidence"))
    ]
    if missing:
        fail(f"claims without claim/source/evidence: {missing[:8]}")
    table = REPO / str(ledger.get("generated_table", ""))
    if not table.exists():
        fail(f"generated table missing: {table}")
    if not (REPO / "docs/reference/known-limitations.md").exists():
        fail("known-limitations.md missing")
    ok(f"claims ledger: {len(claims)} backed claims; generated table + known-limitations present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
