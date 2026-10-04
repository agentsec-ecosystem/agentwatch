#!/usr/bin/env python3
"""Regenerate the harness compatibility table + version-drift baseline (M10 N4 #215).

Reads the shipped-adapter registry in ``agentwatch.compatibility`` and the
conformance fixture packs, then writes ``tests/fixtures/harness-versions.json``
(version tags + shape fingerprints) and rewrites the generated block in
``docs/reference/compatibility.md``. Deterministic: rerunning produces no diff
unless an adapter or fixture shape actually changed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SDK = REPO / "packages" / "python-sdk"
sys.path.insert(0, str(SDK / "src"))

from agentwatch import compatibility  # noqa: E402

FIXTURES = SDK / "tests" / "fixtures"
BASELINE = FIXTURES / "harness-versions.json"
DOC = REPO / "docs" / "reference" / "compatibility.md"


def main() -> int:
    baseline = compatibility.build_baseline(FIXTURES)
    BASELINE.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    DOC.write_text(compatibility.replace_marker_block(doc), encoding="utf-8")
    print(f"wrote {BASELINE.relative_to(REPO)} and updated {DOC.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
