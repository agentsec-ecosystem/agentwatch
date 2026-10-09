"""Public redaction corpus + ``redact eval`` + published numbers (M30 RED-1, #471).

PRD 56 §RED-1, design ``docs/reference/redaction-corpus.md``. A versioned,
public, synthetic corpus drives ``agentwatch redact eval --corpus vN`` to publish
per-class recall and a false-positive rate. The numbers reproduce deterministically
offline, the committed numbers/table cannot drift, known misses are named in
known-limitations, and the corpus is registered for the secret scan.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.redact import (
    CORPUS_SCHEMA,
    evaluate_corpus,
    load_corpus,
    render_report_table,
)

REPO = Path(__file__).resolve().parents[3]
CORPUS = REPO / "schema" / "vectors" / "redaction" / "v1" / "corpus.json"
NUMBERS = REPO / "docs" / "reference" / "redaction-corpus-numbers.json"
DOC = REPO / "docs" / "reference" / "redaction-corpus.md"
KNOWN_LIMITATIONS = REPO / "docs" / "reference" / "known-limitations.md"
DOC_BEGIN = "<!-- BEGIN GENERATED: redaction-corpus-numbers -->"
DOC_END = "<!-- END GENERATED: redaction-corpus-numbers -->"


def _committed_numbers() -> dict[str, object]:
    data: dict[str, object] = json.loads(NUMBERS.read_text(encoding="utf-8"))
    return data


def _doc_block() -> str:
    text = DOC.read_text(encoding="utf-8")
    _, _, rest = text.partition(DOC_BEGIN)
    block, _, _ = rest.partition(DOC_END)
    return block.strip()


def test_corpus_exists_and_declares_its_schema() -> None:
    payload = json.loads(CORPUS.read_text(encoding="utf-8"))
    assert payload["schema"] == CORPUS_SCHEMA
    assert payload["version"] == "v1"
    assert payload["cases"]


def test_eval_is_deterministic_offline() -> None:
    corpus = load_corpus("v1")
    first = evaluate_corpus(corpus).to_dict()
    second = evaluate_corpus(load_corpus("v1")).to_dict()
    assert first == second


def test_published_numbers_reproduce_and_do_not_drift() -> None:
    report = evaluate_corpus(load_corpus("v1"))
    assert report.to_dict() == _committed_numbers()


def test_published_table_is_generated_and_current() -> None:
    report = evaluate_corpus(load_corpus("v1"))
    assert _doc_block() == render_report_table(report).strip()


def test_every_positive_class_is_reported() -> None:
    corpus = load_corpus("v1")
    report = evaluate_corpus(corpus)
    positive_classes = {case.klass for case in corpus.cases if case.label == "positive"}
    assert {result.klass for result in report.classes} == positive_classes


def test_false_positive_rate_is_published() -> None:
    report = evaluate_corpus(load_corpus("v1"))
    assert "false_positive_rate" in report.to_dict()
    assert report.false_positive_rate == 0.0


def test_known_misses_are_listed_as_known_limitations() -> None:
    report = evaluate_corpus(load_corpus("v1"))
    assert report.misses, "the corpus must exercise at least one honest miss"
    limitations = KNOWN_LIMITATIONS.read_text(encoding="utf-8")
    for case_id in report.misses:
        assert case_id in limitations, case_id


def test_corpus_is_registered_for_the_secret_scan() -> None:
    gitleaks = (REPO / ".gitleaks.toml").read_text(encoding="utf-8")
    trufflehog = (REPO / "scripts" / "security" / "trufflehog-exclude.txt").read_text(
        encoding="utf-8"
    )
    assert "schema/vectors/redaction" in gitleaks
    assert "schema/vectors/redaction" in trufflehog


# --------------------------------------------------------------------------- CLI


def test_cli_redact_eval_reproduces_the_numbers(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["redact", "eval", "--corpus", "v1", "--json"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report == _committed_numbers()


def test_cli_redact_eval_renders_a_table(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["redact", "eval", "--corpus", "v1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "recall" in out.lower()
    assert "false-positive" in out.lower()


def test_cli_redact_eval_unknown_corpus_fails(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["redact", "eval", "--corpus", "v99"])
    assert rc != 0
    assert "corpus" in capsys.readouterr().err.lower()
