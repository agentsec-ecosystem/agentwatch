"""Tests for the trust-path mutation gate (PRD 38 §Q2, issue #219).

These exercise the pure budget/allow-list logic and the mutation inventory; the
slow "apply a mutation and run the focused suite" path is covered by the CI job
and by ``python scripts/mutation_gate.py --self-test``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[1]
GATE_PATH = REPO / "scripts" / "mutation_gate.py"


def _load_gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mutation_gate", GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before execution so dataclasses can resolve the module while the
    # decorator runs (it looks itself up in sys.modules).
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


def test_all_killed_passes_with_zero_budget() -> None:
    results = [gate.MutationResult("a", False, 1), gate.MutationResult("b", False, 1)]
    code, survivors = gate.gate_status(results, budget=0, allowlist={})
    assert code == 0
    assert survivors == []


def test_a_survivor_fails_the_zero_budget_gate() -> None:
    results = [gate.MutationResult("a", False, 1), gate.MutationResult("b", True, 0)]
    code, survivors = gate.gate_status(results, budget=0, allowlist={})
    assert code == 1
    assert survivors == ["b"]


def test_survivor_at_budget_passes() -> None:
    results = [gate.MutationResult("b", True, 0)]
    code, survivors = gate.gate_status(results, budget=1, allowlist={})
    assert code == 0
    assert survivors == ["b"]


def test_allowlisted_survivor_is_accounted_for() -> None:
    results = [gate.MutationResult("b", True, 0)]
    code, survivors = gate.gate_status(results, budget=0, allowlist={"b": "equivalent"})
    assert code == 0
    assert survivors == []


def test_mutation_inventory_is_unique_and_complete() -> None:
    ids = [mutation.id for mutation in gate.MUTATIONS]
    assert len(ids) == len(set(ids))
    for mutation in gate.MUTATIONS:
        assert mutation.old
        assert mutation.new != mutation.old
        assert mutation.tests
        assert mutation.rationale
        module = GATE_PATH.parents[1] / "packages" / "python-sdk" / "src" / mutation.module
        assert module.is_file()


def test_self_test_mutation_is_behaviour_preserving() -> None:
    marker = "Redaction and privacy controls"
    assert marker in gate.SELF_TEST_MUTATION.old
    assert marker in gate.SELF_TEST_MUTATION.new
