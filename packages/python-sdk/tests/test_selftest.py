"""Tests for the redaction self-test that gates export (M4 4.6, DD-09)."""

from __future__ import annotations

import pytest

from agentwatch import selftest
from agentwatch.selftest import SELF_TEST_CORPUS, export_allowed, run_redaction_self_test


def test_self_test_passes_for_default_corpus() -> None:
    result = run_redaction_self_test()

    assert result.passed is True
    assert result.checked == len(SELF_TEST_CORPUS)
    assert result.leaks == ()


def test_self_test_blocks_export_when_pipeline_leaks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A broken masking pipeline must leak and therefore block export (F6).
    monkeypatch.setattr(selftest, "redact_mapping", lambda value: (value, ()))

    result = run_redaction_self_test()

    assert result.passed is False
    assert result.leaks
    assert export_allowed() is False
