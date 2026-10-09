#!/usr/bin/env python3
"""Generate the per-detector metrics block in docs/reference/detector-catalog.md.

Runs the offline field-test rule matrix (M26 DET-2/DET-3) and rewrites the block
between the ``detector-metrics`` markers, so the published precision/recall can
never drift from the harness. CI asserts the committed block is current
(``services/analytics/tests/test_detector_catalog.py``).

Usage: python scripts/generate_detector_catalog.py [--check]
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "analytics" / "src"))

from analytics.scenario_validation import render_metrics_table, run_rule_matrix  # noqa: E402

CATALOG = REPO / "docs" / "reference" / "detector-catalog.md"
BEGIN = "<!-- BEGIN GENERATED: detector-metrics -->"
END = "<!-- END GENERATED: detector-metrics -->"


def _replace_block(text: str, block: str) -> str:
    start = text.index(BEGIN) + len(BEGIN)
    end = text.index(END)
    return f"{text[:start]}\n{block}\n{text[end:]}"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    check = "--check" in args
    report = asyncio.run(run_rule_matrix())
    block = render_metrics_table(report)
    text = CATALOG.read_text(encoding="utf-8")
    updated = _replace_block(text, block)
    if check:
        if updated != text:
            print("detector-catalog metrics are stale; run scripts/generate_detector_catalog.py", file=sys.stderr)
            return 1
        print("detector-catalog metrics are current")
        return 0
    CATALOG.write_text(updated, encoding="utf-8")
    print(f"updated {CATALOG.relative_to(REPO)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
