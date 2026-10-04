"""Accessibility conformance statement matches the automated checks (PRD 38 §Q11, #228)."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ACCESSIBILITY = REPO / "docs" / "reference" / "accessibility.md"
UNIT_AXE = REPO / "apps" / "web" / "src" / "__tests__" / "a11y.test.tsx"
E2E_AXE = REPO / "apps" / "web" / "tests" / "e2e" / "a11y.spec.ts"
WORKFLOWS = REPO / ".github" / "workflows"

VIEWS = [
    "Dashboard",
    "Fleet Health",
    "Run Timeline",
    "Agent Detail",
    "Version Compare",
    "Anomaly Inbox",
]


def _doc() -> str:
    return ACCESSIBILITY.read_text(encoding="utf-8")


def test_statement_declares_wcag_22_level_aa() -> None:
    text = _doc()

    assert "WCAG 2.2" in text
    assert "**AA**" in text


def test_statement_lists_every_view_with_a_conformance_row() -> None:
    rows = [line for line in _doc().splitlines() if line.startswith("| ") and "Supports" in line]

    assert len(rows) >= len(VIEWS)
    for view in VIEWS:
        assert any(line.startswith(f"| {view}") for line in rows), f"no VPAT row for {view}"


def test_every_stated_view_is_covered_by_the_unit_axe_suite() -> None:
    covered = UNIT_AXE.read_text(encoding="utf-8")

    for view in VIEWS:
        assert view in covered, f"{view} is claimed but not covered by {UNIT_AXE.name}"


def test_statement_links_the_automated_evidence() -> None:
    text = _doc()

    assert "a11y.test.tsx" in text
    assert "a11y.spec.ts" in text


def test_playwright_check_covers_contrast_and_a_keyboard_journey() -> None:
    spec = E2E_AXE.read_text(encoding="utf-8")

    assert "color-contrast" in spec or "colorContrast" in spec
    assert "keyboard" in spec.lower()
    assert "Enter" in spec


def test_ci_runs_axe_and_playwright() -> None:
    web = (WORKFLOWS / "web.yml").read_text(encoding="utf-8")
    e2e = (WORKFLOWS / "e2e.yml").read_text(encoding="utf-8")
    run_e2e = (REPO / "scripts" / "run-e2e.sh").read_text(encoding="utf-8")

    assert "npm test" in web  # vitest + axe unit suite
    assert "run-e2e.sh" in e2e
    assert "playwright test" in run_e2e
