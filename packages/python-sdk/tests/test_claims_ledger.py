"""Claims ledger: every public claim traces to live evidence (PRD 38 §Q9, #226)."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

REPO = Path(__file__).resolve().parents[3]
CHECKER = REPO / "scripts" / "check_claims.py"
LEDGER = REPO / "docs" / "release" / "claims-ledger.json"
LEDGER_MD = REPO / "docs" / "release" / "claims-ledger.md"


def _load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_claims", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check = _load_checker()
LEDGER_DATA = json.loads(LEDGER.read_text(encoding="utf-8"))


def _ledger_with(claim: dict[str, Any]) -> dict[str, Any]:
    return {"claims": [claim]}


_TEST_REF = "test:packages/python-sdk/tests/test_replay.py::test_replay_orders_by_time_then_chain"
_BASE: dict[str, Any] = {
    "id": "X",
    "claim": "a claim",
    "source": "README.md",
    "evidence": [_TEST_REF],
    "last_verified": "2026-01-01",
}


def test_current_ledger_passes() -> None:
    assert check.validate(LEDGER_DATA, REPO) == []


def test_generated_table_matches_the_ledger() -> None:
    markdown = LEDGER_MD.read_text(encoding="utf-8")
    assert check.extract_block(markdown) == check.render_table(LEDGER_DATA).strip()


def test_claim_without_evidence_fails() -> None:
    errors = check.validate(_ledger_with({**_BASE, "evidence": []}), REPO)
    assert any("no evidence" in error for error in errors)


def test_renamed_test_link_fails() -> None:
    claim = {**_BASE, "evidence": ["test:packages/python-sdk/tests/test_replay.py::test_gone"]}
    errors = check.validate(_ledger_with(claim), REPO)
    assert any("not found" in error for error in errors)


def test_unknown_evidence_type_fails() -> None:
    errors = check.validate(_ledger_with({**_BASE, "evidence": ["mystery:x"]}), REPO)
    assert any("unknown evidence type" in error for error in errors)


def test_missing_file_evidence_fails() -> None:
    claim = {**_BASE, "evidence": ["file:docs/does-not-exist.md"]}
    errors = check.validate(_ledger_with(claim), REPO)
    assert any("file missing" in error for error in errors)


def test_duplicate_ids_fail() -> None:
    errors = check.validate({"claims": [copy.deepcopy(_BASE), copy.deepcopy(_BASE)]}, REPO)
    assert any("duplicate id" in error for error in errors)


def test_future_verified_date_fails() -> None:
    errors = check.validate(_ledger_with({**_BASE, "last_verified": "2999-01-01"}), REPO)
    assert any("in the future" in error for error in errors)


def test_self_test_passes() -> None:
    assert check.self_test(REPO) == []


def test_run_reports_no_problems_for_the_current_ledger() -> None:
    assert check.run(REPO) == []
