"""Compliance mapping + forensic-soundness doc checks (M22 W1/W2/W6, #270/#271/#275)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from agentwatch.forensic import statement

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPLIANCE = REPO_ROOT / "docs" / "compliance"
SOUNDNESS = REPO_ROOT / "docs" / "design" / "forensic-soundness.md"

DOCS = [
    COMPLIANCE / "eu-ai-act-mapping.md",
    COMPLIANCE / "iso-27001-appendix.md",
    COMPLIANCE / "iso-42001-appendix.md",
    COMPLIANCE / "nist-800-92-appendix.md",
    COMPLIANCE / "standard-artifacts.md",
    COMPLIANCE / "openssf-badge.md",
    COMPLIANCE / "advisory-process.md",
    SOUNDNESS,
]

_LINK = re.compile(r"\]\(([^)]+)\)")
_COMMAND = re.compile(r"`agentwatch [^`]+`")


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_doc_exists_and_has_evidence_commands(doc: Path) -> None:
    assert doc.exists(), f"missing {doc}"
    text = doc.read_text(encoding="utf-8")
    assert "Evidence" in text or "evidence" in text


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_relative_links_resolve(doc: Path) -> None:
    text = doc.read_text(encoding="utf-8")
    for target in _LINK.findall(text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        anchor = target.split("#", 1)[0]
        if not anchor:
            continue
        assert (doc.parent / anchor).resolve().exists(), f"{doc.name}: broken link {target}"


def test_eu_ai_act_names_articles_and_disclaims() -> None:
    text = (COMPLIANCE / "eu-ai-act-mapping.md").read_text(encoding="utf-8")
    for article in ("Article 12", "Article 19", "Article 26"):
        assert article in text
    assert "not provide" in text.replace("*", "").lower()
    assert _COMMAND.search(text), "no evidence command in the EU AI Act mapping"


def test_forensic_soundness_states_limits() -> None:
    text = SOUNDNESS.read_text(encoding="utf-8")
    assert "not prove" in text.replace("*", "").lower()
    assert statement()  # the shippable statement exists
    assert "not prove" in statement().replace("*", "").lower()


def test_openssf_self_assessment_lists_criteria() -> None:
    text = (COMPLIANCE / "openssf-badge.md").read_text(encoding="utf-8")
    assert "✅" in text
    assert "SECURITY.md" in text
