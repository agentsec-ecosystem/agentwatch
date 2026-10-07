"""Certified framework recipes (M29 FWK-1, PRD 51 §FWK-1, #446).

Each recipe (Google ADK, Strands Agents, OpenAI Agents SDK via OpenInference, and
the Claude Agent SDK) routes native/community OpenTelemetry into agentwatch
through the *shared* :mod:`agentwatch.ingest` path. The fixtures are shape-derived
from the vendor/community attribute vocabulary; the frameworks are not installable
in this environment, so the live pinned run is **BLOCKED** and every row carries an
honest tier (never ``live-verified``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentwatch import compatibility, conformance, frameworks
from agentwatch.ingest import transcode_otel_detailed
from agentwatch.records import validate_record

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parents[2]
FIXTURES = TESTS / "fixtures" / "frameworks"
DOC = REPO / "docs" / "reference" / "framework-recipes.md"
COMPAT_DOC = REPO / "docs" / "reference" / "compatibility.md"
GALLERY_README = REPO / "examples" / "README.md"
GALLERY_RECIPE = REPO / "examples" / "framework_recipes.py"

FRAMEWORKS = ("adk", "strands", "openai-agents", "claude-agent-sdk")
SOURCES = {"otel-genai", "openinference", "claude-code-otel"}


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "conformance.json").read_text(encoding="utf-8"))


def test_every_recipe_is_pinned_and_tiered() -> None:
    assert set(frameworks.SUPPORTED_FRAMEWORKS) == set(FRAMEWORKS)
    for name in FRAMEWORKS:
        recipe = frameworks.get(name)
        assert recipe.package
        assert recipe.pinned and recipe.pinned not in {"*", "any"}
        assert recipe.source in SOURCES
        assert recipe.tier in compatibility.FIDELITY_TIERS
        assert recipe.cost_keys
        assert recipe.identity_keys
        assert recipe.step_map


def test_every_recipe_is_two_lines_or_one_config_block() -> None:
    for name in FRAMEWORKS:
        assert frameworks.recipe_line_count(name) <= 2


def test_every_recipe_declares_its_blocked_live_run() -> None:
    # The live pinned run cannot happen here; a recipe must say so rather than
    # claim a green live run. Tiers stay modeled (shape-derived, not captured).
    for name in FRAMEWORKS:
        recipe = frameworks.get(name)
        assert recipe.live_verified is False
        assert recipe.tier == compatibility.FIDELITY_MODELED
        assert recipe.blocked_reason


@pytest.mark.parametrize("name", FRAMEWORKS)
def test_recipe_transcodes_fixture_with_explicit_unmapped(name: str) -> None:
    fixture = _fixture(name)

    records, problems, unmapped = transcode_otel_detailed(fixture["input"], source=name)

    assert problems == []
    assert records, f"{name} produced no records"
    for record in records:
        validate_record(record.to_dict())
    observed = [
        {
            "tool": record.tool.name,
            "step_type": record.step_type.value if record.step_type else None,
        }
        for record in records
    ]
    assert observed == fixture["expected"]
    # A vendor/community attribute agentwatch does not understand is surfaced, not
    # silently dropped.
    assert set(fixture["expected_unmapped"]) <= set(unmapped)
    # The attributes the recipe claims to map are not reported as unmapped.
    for key in fixture["mapped"]:
        assert key not in unmapped


@pytest.mark.parametrize("name", FRAMEWORKS)
def test_recipe_maps_identity_step_and_cost(name: str) -> None:
    fixture = _fixture(name)

    records, _, _ = transcode_otel_detailed(fixture["input"], source=name)

    assert any(record.agent.identity == fixture["identity"] for record in records)
    assert any(record.tokens == fixture["tokens"] for record in records)
    assert any(
        record.cost_usd == pytest.approx(fixture["cost_usd"]) for record in records
    )


def test_drift_flags_a_pinned_version_bump() -> None:
    upstream = {recipe.name: recipe.pinned for recipe in frameworks.all_recipes()}
    assert frameworks.drift(upstream) == []

    upstream["adk"] = "999.0.0"
    drift = frameworks.drift(upstream)
    assert drift and any("adk" in entry for entry in drift)


def test_framework_rows_carry_a_tier_in_the_compatibility_matrix() -> None:
    table = compatibility.render_table()
    for name in FRAMEWORKS:
        assert f"`{name}`" in table
        assert compatibility.FRAMEWORKS[name].fidelity in compatibility.FIDELITY_TIERS
    assert compatibility.render_marker_block() in COMPAT_DOC.read_text(encoding="utf-8")


def test_framework_recipes_doc_covers_every_framework() -> None:
    text = DOC.read_text(encoding="utf-8")
    for name in FRAMEWORKS:
        recipe = frameworks.get(name)
        assert recipe.pinned in text
        assert recipe.recipe.splitlines()[0].strip() in text


def test_framework_recipe_is_indexed_in_the_examples_gallery() -> None:
    assert f"[`framework_recipes.py`](framework_recipes.py)" in GALLERY_README.read_text(
        encoding="utf-8"
    )
    assert GALLERY_RECIPE.exists()


def test_framework_sdk_conformance_packs_conform() -> None:
    import framework_conformance_registry  # noqa: F401  (registers the packs)

    conformance.assert_sdk_conform()
    names = {spec.name for spec in conformance.registered_sdks()}
    for name in FRAMEWORKS:
        assert f"framework-{name}" in names


def test_framework_drift_baseline_and_workflow_are_current() -> None:
    baseline = json.loads((FIXTURES / "upstream.json").read_text(encoding="utf-8"))["frameworks"]
    assert frameworks.drift(baseline) == []
    workflow = (REPO / ".github" / "workflows" / "framework-drift.yml").read_text(
        encoding="utf-8"
    )
    assert "check_framework_drift.py" in workflow
    assert "cron" in workflow
