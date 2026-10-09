"""AAT conformance vectors + dual-verifier agreement (M26 AAT-4, #314).

Two independent implementations — ``agentwatch.aat.verify_aat_report`` and the
dependency-free ``schema/vectors/verify_aat.py`` — must match the published
``schema/vectors/aat/expected-verdicts.json``. A divergence is a contract bug.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from agentwatch.aat import verify_aat_report

VECTORS = Path(__file__).resolve().parents[3] / "schema" / "vectors" / "aat"
TABLE = json.loads((VECTORS / "expected-verdicts.json").read_text(encoding="utf-8"))
CASES = TABLE["vectors"]


def _load_standalone() -> ModuleType:
    path = VECTORS.parent / "verify_aat.py"
    spec = importlib.util.spec_from_file_location("verify_aat", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


standalone = _load_standalone()


def _expected(case: dict[str, Any]) -> tuple[bool, tuple[int, ...]]:
    return (case["ok"], tuple(case["failed_entries"]))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_product_verifier_matches_the_verdict_table(case: dict[str, Any]) -> None:
    bundle = json.loads((VECTORS / case["file"]).read_text(encoding="utf-8"))

    report = verify_aat_report(bundle)

    assert (report.ok, tuple(problem.index for problem in report.problems)) == _expected(case)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_standalone_verifier_matches_the_verdict_table(case: dict[str, Any]) -> None:
    verdict = standalone.verify(VECTORS / case["file"])

    assert (verdict.ok, tuple(verdict.failed)) == _expected(case)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_the_two_implementations_agree_on_every_vector(case: dict[str, Any]) -> None:
    bundle = json.loads((VECTORS / case["file"]).read_text(encoding="utf-8"))

    report = verify_aat_report(bundle)
    verdict = standalone.verify(VECTORS / case["file"])

    assert (report.ok, tuple(problem.index for problem in report.problems)) == (
        verdict.ok,
        tuple(verdict.failed),
    )


def test_vector_set_covers_the_required_cases() -> None:
    ids = {case["id"] for case in CASES}
    assert {"valid", "tampered", "unmapped", "unsupported-revision"} <= ids


def test_vector_files_exist_and_are_declared_exactly_once() -> None:
    declared = [case["file"] for case in CASES]
    assert len(declared) == len(set(declared))
    for name in declared:
        assert (VECTORS / name).is_file()
    on_disk = {path.name for path in VECTORS.glob("*.json")} - {"expected-verdicts.json"}
    assert on_disk == set(declared)


def test_standalone_verifier_is_dependency_free() -> None:
    tree = ast.parse((VECTORS.parent / "verify_aat.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "agentwatch" not in imported
