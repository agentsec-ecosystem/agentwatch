"""Compliance + versioning-policy validation (M13 13.6/13.8, PRD 18)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SDK_SRC = ROOT / "packages" / "python-sdk" / "src"
sys.path.insert(0, str(SDK_SRC))

from agentwatch.protocol import STORE_FORMAT_VERSION  # noqa: E402
from agentwatch.records import EVENT_VERSION, SCHEMA_VERSION, SecurityEventType  # noqa: E402

SCHEMA = ROOT / "schema"


def _schema(name: str) -> dict:
    return json.loads((SCHEMA / name).read_text(encoding="utf-8"))


def test_schema_constants_match_the_model() -> None:
    record_schema = _schema("agent-record.schema.json")
    event_schema = _schema("security-event.schema.json")

    assert record_schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION
    assert event_schema["properties"]["event_version"]["const"] == EVENT_VERSION
    assert STORE_FORMAT_VERSION == 1


def test_event_schema_enum_matches_the_model() -> None:
    event_schema = _schema("security-event.schema.json")
    assert set(event_schema["properties"]["type"]["enum"]) == {
        member.value for member in SecurityEventType
    }


def test_compliance_matrix_covers_required_frameworks() -> None:
    text = (ROOT / "docs" / "release" / "v0.1.0" / "compliance-matrix.md").read_text(
        encoding="utf-8"
    )
    for framework in ("OWASP", "NIST SSDF", "NIST AI RMF", "ISO/IEC 42001", "SOC 2", "OpenSSF"):
        assert framework in text, framework
    # Honest non-claims are published.
    assert "Not a certified product" in text


def test_open_source_checklist_marks_release_artifacts_done() -> None:
    text = (ROOT / "docs" / "reference" / "open-source-checklist.md").read_text(encoding="utf-8")
    assert "Signed releases + SBOM + provenance | ✅" in text
    assert "Release notes + security audit per version | ✅" in text


def test_versioning_and_backwards_compat_policies_exist_and_are_additive() -> None:
    versioning = (ROOT / "docs" / "reference" / "versioning-policy.md").read_text(encoding="utf-8")
    backwards = (ROOT / "docs" / "reference" / "backwards-compatibility-policy.md").read_text(
        encoding="utf-8"
    )
    assert "SemVer" in versioning
    assert "additive" in backwards.lower()
    assert "deprecation" in backwards.lower()
