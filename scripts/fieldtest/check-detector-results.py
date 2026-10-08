#!/usr/bin/env python3
"""Assert the FT-15 detector boundary-matrix results (M23 §10 criteria).

Reads ``detector-results.json`` (written by ``analytics.scenario_validation``)
and exits nonzero if any scenario failed or any detector has TPR < 95% or
FPR > 5%.
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check-detector-results.py <detector-results.json>", file=sys.stderr)
        return 2
    d = json.load(open(sys.argv[1]))
    bad = {
        k: {"tpr": v["tpr"], "fpr": v["fpr"]}
        for k, v in d["per_detector"].items()
        if (v["tpr"] is not None and v["tpr"] < 95) or (v["fpr"] is not None and v["fpr"] > 5)
    }
    print(
        f"detector-results: mode={d.get('mode')} total={d['total']} "
        f"failed={d['failed']} detectors={len(d['per_detector'])}"
    )
    print(f"  detectors with TPR<95 or FPR>5: {bad or 'none'}")
    if d["failed"] or bad:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
