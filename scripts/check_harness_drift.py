#!/usr/bin/env python3
"""Fail when a harness fixture shape drifts from the committed baseline (M10 N4 #215).

Run nightly (``.github/workflows/harness-drift.yml``): a non-zero exit means a
harness's native event shape changed (or a fixture was added/removed) since the
release baseline was captured. The workflow turns that into an issue — drift is
never applied silently.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SDK = REPO / "packages" / "python-sdk"
sys.path.insert(0, str(SDK / "src"))

from agentwatch import compatibility  # noqa: E402

FIXTURES = SDK / "tests" / "fixtures"
BASELINE = FIXTURES / "harness-versions.json"


def main() -> int:
    baseline = compatibility.load_baseline(BASELINE)
    drift = compatibility.detect_drift(FIXTURES, baseline)
    if drift:
        print("harness drift detected:")
        for item in drift:
            print(f"  - {item}")
        return 1
    print("no harness drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
