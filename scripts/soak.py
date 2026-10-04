#!/usr/bin/env python3
"""Bounded nightly soak (M12 K4, NFR-7): size, verify time, peak memory."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SDK = REPO / "packages" / "python-sdk"
sys.path.insert(0, str(SDK / "src"))

from agentwatch.soak import run_soak  # noqa: E402

COUNT = 20000


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        report = run_soak(Path(directory) / "records.jsonl", count=COUNT)
    print(
        f"soak: {report.records} records; size {report.size_mb} MB; "
        f"verify {report.verify_seconds:.3f}s; peak {report.peak_mb} MB"
    )
    return 0 if report.within_bounds else 1


if __name__ == "__main__":
    raise SystemExit(main())
