"""Guard the CI workflow against regressing to the starter placeholder.

Issue #13 requires CI to actually run ruff, mypy --strict, and pytest with the
coverage gate. These tests fail if the placeholder step returns.
"""

from __future__ import annotations

from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[3] / ".github" / "workflows"
CI_WORKFLOW = WORKFLOWS / "ci.yml"


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


def test_offline_e2e_workflow_runs_the_offline_scripts() -> None:
    text = (WORKFLOWS / "offline-e2e.yml").read_text(encoding="utf-8")
    assert "scripts/offline_e2e.py" in text
    assert "scripts/dependency_egress_audit.py" in text
    assert "unshare" in text


def test_soak_workflow_runs_the_soak_script() -> None:
    text = (WORKFLOWS / "soak.yml").read_text(encoding="utf-8")
    assert "scripts/soak.py" in text
    assert "schedule" in text and "cron" in text


def test_web_workflow_runs_unit_axe_and_typecheck() -> None:
    text = (WORKFLOWS / "web.yml").read_text(encoding="utf-8")
    assert "npm ci" in text
    assert "npm run typecheck" in text
    assert "npm test" in text
    # axe checks are part of the vitest suite (apps/web/src/__tests__/a11y.test.tsx).
    assert "accessibility" in text.lower() or "axe" in text.lower()


def test_e2e_workflow_runs_playwright_against_the_stack() -> None:
    text = (WORKFLOWS / "e2e.yml").read_text(encoding="utf-8")
    assert "scripts/run-e2e.sh" in text
    assert "playwright install" in text
    assert "docker compose" in text


def test_stack_smoke_workflow_boots_the_compose_stack() -> None:
    text = (WORKFLOWS / "stack-smoke.yml").read_text(encoding="utf-8")
    assert "scripts/stack-smoke.sh" in text


def test_claims_workflow_runs_the_ledger_check() -> None:
    text = (WORKFLOWS / "claims.yml").read_text(encoding="utf-8")
    assert "scripts/check_claims.py" in text
    assert "--self-test" in text


def test_executable_docs_workflow_runs_the_cookbook_check() -> None:
    text = (WORKFLOWS / "docs.yml").read_text(encoding="utf-8")
    assert "scripts/check_docs_commands.py" in text
    assert "--self-test" in text


def test_every_workflow_pins_the_checkout_action() -> None:
    import re

    for path in WORKFLOWS.glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"actions/checkout@(\S+)", text):
            pin = match.group(1)
            assert re.fullmatch(r"[0-9a-f]{40}", pin), (
                f"{path.name} does not pin actions/checkout by commit SHA: {pin}"
            )
