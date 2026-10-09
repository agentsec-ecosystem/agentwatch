#!/usr/bin/env python3
"""Honest-tiers guard for the compatibility matrix (XHT-4 / FT-MATRIX-1).

The v0.2.0 release gate (PRD 40 §5.3) forbids a **"modeled"** fidelity row on a
**Tier-1** harness. This reads the generator's own rows
(`agentwatch.compatibility.ALL_ROWS`, the single source of truth that renders
`docs/reference/compatibility.md`) and fails if any Tier-1 row is still modeled —
so the claim cannot pass while a modeled Tier-1 row survives.

Runs both inside the recorder (/work SDK on sys.path) and on the host
(`PYTHONPATH` set by the caller to the in-repo SDK).
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _cand in (
    "/work/packages/python-sdk/src",
    os.path.join(_HERE, "..", "..", "packages", "python-sdk", "src"),
):
    if os.path.isdir(_cand):
        sys.path.insert(0, _cand)

from agentwatch.compatibility import ALL_ROWS, FIDELITY_MODELED  # noqa: E402


def main() -> int:
    bad: list[tuple[str, str]] = []
    for name, info in ALL_ROWS.items():
        # A declared tier is provisional/modeled *by declaration* (PRD 40 §5.3
        # allows "real captures or declared tiers") — not a hidden modeled claim.
        if getattr(info, "declared", False):
            continue
        tier = str(getattr(info, "tier", "")).lower()
        if tier.startswith("tier-1") and info.fidelity == FIDELITY_MODELED:
            bad.append((name, info.tier))
    if bad:
        for name, tier in bad:
            print(f"modeled {tier} row survives: {name}", file=sys.stderr)
        print(f"FAIL: {len(bad)} modeled Tier-1 row(s) — a non-modeled tier or a "
              f"declared gap is required (PRD 40 §5.3)", file=sys.stderr)
        return 1
    print("ok: no modeled Tier-1 row survives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
