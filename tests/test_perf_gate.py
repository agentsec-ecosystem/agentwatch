"""Tests for the performance gate (PRD 38 §Q4, issue #221).

Exercises the pure comparison logic (NFR cap + drift band + floor); the measured
run and its seeded-slowdown proof are covered by the CI job and
``python scripts/perf_gate.py --self-test``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[1]
GATE_PATH = REPO / "scripts" / "perf_gate.py"
BASELINE_PATH = REPO / "perf" / "baseline.json"


def _load_gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("perf_gate", GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


def test_within_budget_and_drift_passes() -> None:
    code, violations = gate.evaluate({"normalize": 0.01}, {"normalize": 0.009})
    assert code == 0
    assert violations == []


def test_over_nfr_cap_fails() -> None:
    code, violations = gate.evaluate({"normalize": 6.0}, {"normalize": 0.009})
    assert code == 1
    assert any("budget" in v for v in violations)


def test_drift_beyond_band_fails() -> None:
    # Baseline 3 ms, tolerance 3x => threshold 9 ms (above the 5 ms cap only
    # matters for the drift wording); use a baseline under the cap and a value
    # over the floor * tolerance.
    code, violations = gate.evaluate({"stage": 4.9}, {"stage": 1.0})
    assert code == 1
    assert any("drift threshold" in v for v in violations)


def test_fast_stage_below_floor_is_not_drift() -> None:
    # A noisy micro-stage under the floor must not trip the drift check.
    code, violations = gate.evaluate({"stage": 0.4}, {"stage": 0.01})
    assert code == 0
    assert violations == []


def test_missing_baseline_only_checks_the_cap() -> None:
    code, _ = gate.evaluate({"new-stage": 1.0}, {})
    assert code == 0
    code, violations = gate.evaluate({"new-stage": 9.0}, {})
    assert code == 1
    assert any("budget" in v for v in violations)


def test_every_scenario_has_an_explicit_budget() -> None:
    assert set(gate.SCENARIO_BUDGETS_MS) == set(gate.SCENARIOS)


def test_new_path_budgets_are_enforced() -> None:
    # otlp_protobuf's cap is 10 ms; 50 ms must fail even though the NFR cap is 5 ms.
    code, violations = gate.evaluate({"otlp_protobuf": 50.0}, {})
    assert code == 1
    assert any("otlp_protobuf" in v and "10.000" in v for v in violations)
    # live_tail_poll's cap is 25 ms; 20 ms must pass.
    code, violations = gate.evaluate({"live_tail_poll": 20.0}, {})
    assert code == 0
    assert violations == []


def test_committed_baseline_covers_every_scenario() -> None:
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert set(data["baseline_ms"]) == set(gate.SCENARIOS)
    assert data["budget_ms"] == gate.NFR_BUDGET_MS
