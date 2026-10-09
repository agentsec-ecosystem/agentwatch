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
    argv = sys.argv[1:]
    flags = {a for a in argv if a.startswith("--")}
    paths = [a for a in argv if not a.startswith("--")]
    if len(paths) != 1:
        print("usage: check-detector-results.py [--nonsilent-80] <detector-results.json>", file=sys.stderr)
        return 2
    d = json.load(open(paths[0]))

    if "--nonsilent-80" in flags:
        # DET-2: >=80% of rule detectors must be non-silent (fire on >=1 positive).
        detectors = d["per_detector"]
        nonsilent = [k for k, v in detectors.items() if (v.get("tp", 0) + v.get("fp", 0)) > 0]
        ratio = (len(nonsilent) / len(detectors)) if detectors else 0.0
        print(f"detector-results: detectors={len(detectors)} non-silent={len(nonsilent)} ({ratio:.0%})")
        silent = sorted(set(detectors) - set(nonsilent))
        print(f"  silent detectors: {silent or 'none'}")
        if d["failed"] or ratio < 0.80:
            return 1
        return 0

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
