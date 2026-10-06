"""Generated detector metrics in the catalog (M26 DET-3, #322).

`docs/reference/detector-catalog.md` publishes per-detector precision/recall
generated from the field-test rule matrix. This test regenerates the block and
asserts it matches the committed doc, so the published numbers cannot drift.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from analytics.scenario_validation import render_metrics_table, run_rule_matrix

CATALOG = Path(__file__).resolve().parents[3] / "docs" / "reference" / "detector-catalog.md"
BEGIN = "<!-- BEGIN GENERATED: detector-metrics -->"
END = "<!-- END GENERATED: detector-metrics -->"


def _committed_block() -> str:
    text = CATALOG.read_text(encoding="utf-8")
    match = re.search(re.escape(BEGIN) + r"\n(.*?)\n" + re.escape(END), text, re.DOTALL)
    assert match is not None, "catalog is missing the generated detector-metrics block"
    return match.group(1)


def test_catalog_detector_metrics_are_generated_and_current() -> None:
    report = asyncio.run(run_rule_matrix())
    expected = render_metrics_table(report)

    assert _committed_block().strip() == expected.strip()


def test_catalog_lists_every_rule_detector() -> None:
    report = asyncio.run(run_rule_matrix())
    block = _committed_block()

    for detector in report["per_detector"]:
        assert f"`{detector}`" in block, detector
