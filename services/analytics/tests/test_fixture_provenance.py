"""Detector fixture provenance (M28 COR-4, #359).

Standing practice: every benchmark-sourced corpus case is shape-synthesized and
cites a public source, and additions are logged. This guards the citation
registry against a new benchmark source tag appearing without a citation.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CORPUS = REPO / "schema" / "vectors" / "detectors" / "detector-corpus-v1.json"
PROVENANCE = REPO / "docs" / "reference" / "detector-fixtures.md"


def _provenance() -> str:
    return PROVENANCE.read_text(encoding="utf-8")


def _benchmark_sources() -> set[str]:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    return {str(source) for source in data.get("sources", []) if str(source).endswith("-shape")}


def test_every_benchmark_source_is_cited() -> None:
    text = _provenance()
    sources = _benchmark_sources()

    assert sources, "the corpus should carry benchmark-sourced cases"
    for source in sources:
        assert f"`{source}`" in text, f"source {source!r} has no citation row"


def test_provenance_states_shape_synthesized_only() -> None:
    text = _provenance().lower()

    assert "shape-synthesized" in text
    assert "no secrets" in text


def test_provenance_has_a_changelog() -> None:
    text = _provenance()

    assert "## Changelog" in text
    assert "## Source registry" in text
