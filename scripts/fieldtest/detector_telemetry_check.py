#!/usr/bin/env python3
"""DET-5: detector telemetry is OFF by default, and when enabled its markers are
content-free (no arguments/prompt/trace/span content) and bounded."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, "/work/packages/python-sdk/src")
from _ftutil import fail, ok  # noqa: E402

from agentwatch.detector_telemetry import (  # noqa: E402
    OUTCOME_FALSE_POSITIVE,
    OUTCOME_FIRED,
    DetectorTelemetry,
)

_ALLOWED = {"kind", "detector", "outcome", "at", "severity"}


def main(argv: list[str]) -> int:
    work = Path(tempfile.mkdtemp(prefix="ft-det5-"))

    off = work / "off.ndjson"
    disabled = DetectorTelemetry(path=off)  # enabled defaults to False
    if disabled.record("loop", OUTCOME_FIRED) is not None:
        fail("disabled telemetry returned a marker")
    if off.exists():
        fail("telemetry wrote a file while disabled (must be off by default)")

    on = work / "on.ndjson"
    enabled = DetectorTelemetry(enabled=True, path=on, max_markers=5)
    enabled.record("loop", OUTCOME_FIRED, severity="high", at=datetime.now(timezone.utc))
    lines = on.read_text(encoding="utf-8").splitlines()
    marker = json.loads(lines[0])
    extra = set(marker) - _ALLOWED
    if extra:
        fail(f"marker carries non-content-free keys: {sorted(extra)}")
    for _ in range(10):
        enabled.record("loop", OUTCOME_FALSE_POSITIVE)
    count = len(on.read_text(encoding="utf-8").splitlines())
    if count > 5:
        fail(f"telemetry is unbounded: {count} markers > max 5")
    ok(f"telemetry off by default; enabled markers are content-free ({sorted(_ALLOWED)}); bounded to {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
