"""Compatibility matrix: managed-policy column + framework rows (M29 EXT-7, #454).

The matrix must state the truth about managed-policy environments (a normal
Claude Code install is blocked under `allowManagedHooksOnly`; DEP-1 adds a
managed path) and about the new instrumentation frameworks. Framework rows are a
**generator input that WS-D (FWK-1) populates**; they are not shipped adapters,
so the conformance registry is unaffected.
"""

from __future__ import annotations

from pathlib import Path

from agentwatch import compatibility

REPO = Path(__file__).resolve().parents[3]
DOC = REPO / "docs" / "reference" / "compatibility.md"


def test_managed_policy_column_is_in_the_table() -> None:
    table = compatibility.render_table()
    assert "Managed policy" in table
    assert "| Harness | Tier | Tested range | Protocol | Fidelity | Managed policy |" in table


def test_every_shipped_row_carries_a_managed_policy_value() -> None:
    for name, info in compatibility.SHIPPED.items():
        assert info.managed_policy in compatibility.MANAGED_POLICY_STATUSES, name


def test_claude_code_is_honest_about_managed_hooks_only() -> None:
    claude = compatibility.SHIPPED["claude-code"]

    assert claude.managed_policy == compatibility.MANAGED_BLOCKED
    assert "managed hook" in claude.notes.lower() or "managed/plugin" in claude.notes.lower()


def test_framework_rows_are_a_ws_d_input() -> None:
    assert set(compatibility.FRAMEWORKS) == {
        "google-adk",
        "strands",
        "openai-agents-sdk",
        "claude-agent-sdk",
    }
    for name, row in compatibility.FRAMEWORKS.items():
        assert row.fidelity in compatibility.FIDELITY_TIERS, name
        assert row.managed_policy in compatibility.MANAGED_POLICY_STATUSES, name
        assert "WS-D" in row.populated_by, name


def test_framework_rows_are_not_shipped_adapters() -> None:
    # The conformance registry covers shipped adapters only (test_compatibility
    # asserts registered == set(SHIPPED)); frameworks must not leak in.
    assert set(compatibility.FRAMEWORKS).isdisjoint(set(compatibility.SHIPPED))


def test_frameworks_are_rendered_in_the_table() -> None:
    table = compatibility.render_table()
    for name in compatibility.FRAMEWORKS:
        assert f"`{name}`" in table


def test_doc_has_the_regenerated_block() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert compatibility.render_marker_block() in text
    assert "Managed policy" in text
    assert "`google-adk`" in text
