"""Store/chain conformance vectors (PRD 38 §Q6, issue #223).

Both implementations — ``agentwatch.store.RecordStore.verify`` and the
dependency-free ``schema/vectors/verify_store.py`` — must match the published
``expected-verdicts.json`` table. A divergence is a contract bug.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from agentwatch.store import RecordStore

VECTORS = Path(__file__).resolve().parents[3] / "schema" / "vectors" / "store"
TABLE = json.loads((VECTORS / "expected-verdicts.json").read_text(encoding="utf-8"))
CASES = TABLE["vectors"]


def _load_standalone() -> ModuleType:
    path = VECTORS.parent / "verify_store.py"
    spec = importlib.util.spec_from_file_location("verify_store", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


standalone = _load_standalone()


def _expected(case: dict[str, Any]) -> tuple[bool, int | None, int | None]:
    return (case["ok"], case["broken_at"], case["line"])


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_store_verify_matches_the_verdict_table(case: dict[str, Any]) -> None:
    status = RecordStore(VECTORS / case["file"], durability="none").verify()

    assert (status.ok, status.broken_at, status.line) == _expected(case)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_standalone_verifier_matches_the_verdict_table(case: dict[str, Any]) -> None:
    verdict = standalone.verify(VECTORS / case["file"])

    assert (verdict.ok, verdict.broken_at, verdict.line) == _expected(case)


def test_vector_set_covers_the_required_cases() -> None:
    ids = {case["id"] for case in CASES}
    assert {
        "valid",
        "tampered",
        "tombstoned",
        "purged",
        "gap",
        "checkpoint",
    } <= ids


def test_vector_files_exist_and_are_declared_exactly_once() -> None:
    declared = [case["file"] for case in CASES]
    assert len(declared) == len(set(declared))
    for name in declared:
        assert (VECTORS / name).is_file()
    on_disk = {path.name for path in VECTORS.glob("*.jsonl")}
    assert on_disk == set(declared)


def test_the_two_implementations_agree_on_every_vector() -> None:
    for case in CASES:
        path = VECTORS / case["file"]
        status = RecordStore(path, durability="none").verify()
        verdict = standalone.verify(path)
        assert (status.ok, status.broken_at) == (verdict.ok, verdict.broken_at)
