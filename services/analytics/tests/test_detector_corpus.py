"""Public detector-eval corpus v1 (M26 COR-1, #323).

The corpus must be versioned, machine-checkable (every case's verdict comes out
as authored), governance-clean (no real secrets/PII — shape-synthesized only),
and drift-guarded against its generator.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

import pytest

from analytics.scenario_validation import export_public_corpus

CORPUS = (
    Path(__file__).resolve().parents[3]
    / "schema"
    / "vectors"
    / "detectors"
    / "detector-corpus-v1.json"
)


def _load() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(CORPUS.read_text(encoding="utf-8")))


def test_corpus_is_versioned_and_populated() -> None:
    data = _load()

    assert data["schema"] == "agentwatch.detector-corpus/1"
    assert data["version"] == "1"
    assert data["vocabulary"] == "draft-han-bmwg-agent-security-benchmark"
    assert len(data["cases"]) == 147
    assert set(data["sources"]) >= {"field-test-scenarios", "benign-traffic"}


def test_every_rule_detector_has_a_case() -> None:
    from analytics.detectors.eval import detector_classes

    detectors = {case["detector"] for case in _load()["cases"]}

    assert detectors == set(detector_classes())


def test_corpus_cases_are_machine_checkable() -> None:
    from analytics.detectors.eval import check_public_corpus, load_public_corpus

    corpus = load_public_corpus(CORPUS)
    results = check_public_corpus(corpus)

    assert len(results) == 147
    failed = [r.id for r in results if not r.ok]
    assert failed == [], failed


def test_corpus_is_governance_clean() -> None:
    pytest.importorskip("agentwatch")
    from agentwatch.secrets import detect

    text = CORPUS.read_text(encoding="utf-8")
    assert detect(text) == []
    # No obvious PII shapes in shape-synthesized fixtures.
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    assert not re.search(r"\b\d{3}[-.]\d{3}[-.]\d{4}\b", text)


def test_corpus_matches_its_generator() -> None:
    assert _load() == export_public_corpus()
