"""Compatibility table + version-drift matrix tests (M10 N4 #215)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import conformance_registry  # noqa: F401  (registers shipped adapters)
import pytest

from agentwatch import compatibility, conformance

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parents[2]
FIXTURES = TESTS / "fixtures"
BASELINE = FIXTURES / "harness-versions.json"
DOC = REPO / "docs" / "reference" / "compatibility.md"
WORKFLOW = REPO / ".github" / "workflows" / "harness-drift.yml"


def test_registry_covers_every_shipped_adapter() -> None:
    registered = {spec.name for spec in conformance.registered()}
    assert registered == set(compatibility.SHIPPED)


def test_table_is_deterministic_and_sorted() -> None:
    table = compatibility.render_table()
    assert table == compatibility.render_table()
    positions = [table.index(f"`{name}`") for name in sorted(compatibility.SHIPPED)]
    assert positions == sorted(positions)


def test_claude_code_range_is_declared() -> None:
    assert compatibility.range_for("claude-code").minimum == "2.0"
    with pytest.raises(KeyError):
        compatibility.range_for("nonexistent")


def test_generated_block_is_present_in_the_doc() -> None:
    assert compatibility.render_marker_block() in DOC.read_text(encoding="utf-8")


def test_committed_baseline_is_up_to_date() -> None:
    assert compatibility.load_baseline(BASELINE) == compatibility.build_baseline(FIXTURES)


def test_fingerprint_is_value_independent() -> None:
    shape = {"phase": "pre", "event": {"session_id": "x", "tool_name": "y"}}
    other = {"phase": "post", "event": {"session_id": "a", "tool_name": "b"}}
    assert compatibility.fixture_fingerprint({"message": shape}) == (
        compatibility.fixture_fingerprint({"message": other})
    )


def test_detect_drift_flags_a_shape_change(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    for harness in ("cursor",):
        shutil.copytree(FIXTURES / harness, root / harness)
    baseline = compatibility.build_baseline(root)
    assert compatibility.detect_drift(root, baseline) == []

    path = root / "cursor" / "before_shell.json"
    fixture = json.loads(path.read_text())
    fixture["message"]["event"]["new_field"] = 1  # a shape change
    path.write_text(json.dumps(fixture), encoding="utf-8")

    drift = compatibility.detect_drift(root, baseline)
    assert drift and "shape changed" in drift[0]


def test_detect_drift_flags_added_and_removed(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    shutil.copytree(FIXTURES / "cursor", root / "cursor")
    baseline = compatibility.build_baseline(root)

    extra = root / "cursor" / "extra.json"
    extra.write_text(json.dumps({"message": {"phase": "x"}, "expected": []}), encoding="utf-8")
    (root / "cursor" / "after_edit_error.json").unlink()

    drift = compatibility.detect_drift(root, baseline)
    assert any("added fixture" in item for item in drift)
    assert any("removed fixture" in item for item in drift)


def test_nightly_drift_workflow_runs_the_check() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "check_harness_drift.py" in text
    assert "schedule" in text and "cron" in text
    assert "gh issue create" in text
