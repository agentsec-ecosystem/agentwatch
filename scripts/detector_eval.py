#!/usr/bin/env python3
"""Run the internal detector-eval corpus (M25 DET-1, #302).

Offline, deterministic, no network. Drives the real analytics detectors over
``services/analytics/data/detector-corpus-v0.json`` and prints per-detector
precision/recall. CI uses this as the detector-eval gate.

Usage::

    python scripts/detector_eval.py [--corpus PATH] [--json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "analytics" / "src"))

from analytics.detectors.eval import load_corpus, run_eval  # noqa: E402

DEFAULT_CORPUS = REPO / "services" / "analytics" / "data" / "detector-corpus-v0.json"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in args
    rest = [arg for arg in args if arg != "--json"]
    corpus = Path(rest[0]) if rest else DEFAULT_CORPUS

    cases = load_corpus(corpus)
    report = run_eval(cases)
    rows = {
        detector: {
            "precision": round(report.precision(detector), 4),
            "recall": round(report.recall(detector), 4),
        }
        for detector in report.detectors()
    }
    if as_json:
        print(json.dumps({"corpus": corpus.name, "detectors": rows}, sort_keys=True))
    else:
        for detector, row in rows.items():
            print(f"{detector}: precision={row['precision']} recall={row['recall']}")
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())