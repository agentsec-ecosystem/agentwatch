"""Guard the CI workflow against regressing to the starter placeholder.

Issue #13 requires CI to actually run ruff, mypy --strict, and pytest with the
coverage gate. These tests fail if the placeholder step returns.
"""

from __future__ import annotations

from pathlib import Path

CI_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"


def _text() -> str:
    return CI_WORKFLOW.read_text(encoding="utf-8")


def test_placeholder_step_is_gone() -> None:
    assert "Placeholder" not in _text()
    assert "TODO: replace with real lint/test commands" not in _text()


def test_ci_installs_python_and_runs_quality_gates() -> None:
    text = _text()
    assert "actions/setup-python" in text
    assert "make lint" in text
    assert "make typecheck" in text
    assert "make test" in text


def test_ci_runs_across_supported_python_versions() -> None:
    text = _text()
    assert "3.10" in text
    assert "3.12" in text
