"""Claude Code adapter conformance (M3 #29).

Fixture replay: native hook messages -> expected normalized records. Gap
assertions: declared-unsupported capability classes are rejected explicitly,
never dropped silently.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agentwatch.adapters import claude_code
from agentwatch.records import validate_record

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "claude-code"
CASES = sorted(FIXTURES.glob("*.json"))


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def test_conformance_fixtures_are_populated() -> None:
    assert CASES, "no conformance fixtures found"


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.stem)
def test_fixture_replay_matches_expected_records(path: Path) -> None:
    fixture = _load(path)
    records = claude_code.normalize(fixture["message"])

    assert [record.to_dict() for record in records] == fixture["expected"]
    for record in records:
        validate_record(record.to_dict())


def test_declared_gaps_are_disjoint_from_capabilities() -> None:
    assert claude_code.DOCUMENTED_GAPS
    assert set(claude_code.DOCUMENTED_GAPS).isdisjoint(claude_code.CAPABILITIES)


def test_unsupported_capability_phase_is_rejected() -> None:
    with pytest.raises(claude_code.ClaudeCodeAdapterError):
        claude_code.normalize({"phase": "session-end", "event": {"session_id": "s"}})


@pytest.mark.parametrize("gap", claude_code.DOCUMENTED_GAPS)
def test_each_declared_gap_is_rejected_explicitly(gap: str) -> None:
    # A documented-gap capability class must be rejected, never dropped silently.
    with pytest.raises(claude_code.ClaudeCodeAdapterError):
        claude_code.normalize({"phase": gap, "event": {"session_id": "s"}})
