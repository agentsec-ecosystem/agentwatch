"""STD-1 standards participation plan + DD-05 closure (M29 #452).

The plan is a published governance artifact with an owner and a quarterly
re-pin/engagement cadence; DD-05 is closed by ADR-0045; and every target spec
has at least one upstream contribution tracked in the claims ledger as
"submitted" — never "adopted".
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[3]
PLAN = REPO / "docs" / "reference" / "standards-participation.md"
DD = REPO / "docs" / "design" / "design-decisions.md"
ADR = REPO / "docs" / "adr" / "0045-standards-participation.md"
ADR_README = REPO / "docs" / "adr" / "README.md"
LEDGER = REPO / "docs" / "release" / "claims-ledger.json"
CHECK_CLAIMS = REPO / "scripts" / "check_claims.py"

# The target specs the plan commits to (PRD 59 §STD-1).
TARGET_SPECS = ("OTel GenAI semconv", "IETF AAT", "Agent Trace", "OCSF", "OWASP Agentic")


def _load_check_claims() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_claims", CHECK_CLAIMS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_plan_exists_with_owner_specs_proposals_and_cadence() -> None:
    assert PLAN.exists(), f"missing {PLAN}"
    text = PLAN.read_text(encoding="utf-8")
    lowered = text.lower()

    for spec in TARGET_SPECS:
        assert spec in text, f"plan does not name target spec {spec!r}"
    for needle in (
        "owner",
        "quarterly",
        "capability-changed",
        "authorization taxonomy v2",
        "event vocabulary",
        "submitted",
        "adopter",
    ):
        assert needle in lowered, f"plan is missing {needle!r}"
    assert "not adopted" in lowered or "never adopted" in lowered


def test_dd05_is_closed_by_adr_0045() -> None:
    text = DD.read_text(encoding="utf-8")
    row = next(
        (line for line in text.splitlines() if line.startswith("| DD-05")),
        None,
    )
    assert row is not None, "DD-05 row missing from the decision log"
    assert "closed" in row.lower(), f"DD-05 not closed: {row}"
    assert "0045" in row, f"DD-05 does not cite ADR-0045: {row}"

    assert ADR.exists(), f"missing {ADR}"
    adr = ADR.read_text(encoding="utf-8")
    assert "DD-05" in adr
    assert "accepted" in adr.lower()
    assert "0045" in ADR_README.read_text(encoding="utf-8")


def test_ledger_tracks_a_submission_per_target_spec_never_adopted() -> None:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    submitted = [
        claim for claim in ledger["claims"] if "submitted" in str(claim["claim"]).lower()
    ]
    assert len(submitted) >= len(TARGET_SPECS)
    joined = " ".join(str(claim["claim"]) for claim in submitted)
    for spec in TARGET_SPECS:
        assert spec in joined, f"no 'submitted' ledger claim names {spec!r}"

    for claim in submitted:
        text = str(claim["claim"]).lower()
        text = text.replace("never adopted", "").replace("not adopted", "")
        assert "adopt" not in text, f"submission claims adoption: {claim['claim']!r}"


def test_ledger_evidence_resolves() -> None:
    check = _load_check_claims()
    problems = check.validate(check.load_ledger())
    assert problems == []