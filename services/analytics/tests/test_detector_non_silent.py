"""Rule-detector non-silent coverage gate (M26 DET-2, #321).

Runs the *rule* detectors over the field-test scenario matrix (offline, scripted
pool) and asserts:

* the whole boundary + precision matrix passes (no fire/severity/type/evidence
  regressions), and
* at least 80% of rule detectors fire on their positive scenarios (the DET-2
  "no silent detectors" target).

This replaces the thin 5-case internal corpus as the coverage gate; the per-case
public corpus stays the job of COR-1.
"""

from __future__ import annotations

import asyncio

from analytics.scenario_validation import LLM_DETECTORS, rule_coverage, run_rule_matrix


def test_rule_matrix_passes_offline() -> None:
    report = asyncio.run(run_rule_matrix())

    assert report["failed"] == 0, [
        r["id"] for r in report["scenarios"] if not r["ok"]
    ]


def test_rule_detectors_are_non_silent() -> None:
    report = asyncio.run(run_rule_matrix())
    coverage = rule_coverage(report)

    assert coverage["total"] >= 30
    assert coverage["fraction"] >= coverage["target"], coverage
    assert coverage["silent"] == [], coverage


def test_llm_detectors_are_excluded_from_the_rule_gate() -> None:
    report = asyncio.run(run_rule_matrix())
    detectors = set(report["per_detector"])

    assert detectors.isdisjoint(LLM_DETECTORS)
