"""Golden corpus of harness events (M8 addition I2).

A version-tagged corpus replayed against the adapter in CI, so a harness event
shape change fails a fixture instead of a user. Real captures (from an
authenticated machine) live under ``golden/real/`` and are replayed when present
or skipped with an explicit reason here. Every fixture is scanned for secrets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agentwatch.adapters import claude_code
from agentwatch.records import validate_record
from agentwatch.secrets import detect

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "claude-code" / "golden"
MANIFEST = GOLDEN / "manifest.json"
REAL = GOLDEN / "real"


def _manifest() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return data


def _cases() -> list[Path]:
    return [GOLDEN / name for name in _manifest()["cases"]]


def test_manifest_is_version_tagged() -> None:
    manifest = _manifest()

    assert manifest["harness"] == "claude-code"
    assert manifest["harness_version"]


@pytest.mark.parametrize("path", _cases(), ids=lambda p: p.stem)
def test_golden_cases_replay(path: Path) -> None:
    fixture = json.loads(path.read_text(encoding="utf-8"))

    records = claude_code.normalize(fixture["message"])

    assert [record.to_dict() for record in records] == fixture["expected"]
    for record in records:
        validate_record(record.to_dict())


def test_real_capture_corpus_replays_or_skips() -> None:
    real = sorted(REAL.glob("*.json")) if REAL.exists() else []
    if not real:
        pytest.skip(
            "no authenticated capture yet; refresh the corpus with "
            "scripts/capture-golden.py on a machine running Claude Code"
        )
    for path in real:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        records = claude_code.normalize(fixture["message"])
        assert [record.to_dict() for record in records] == fixture["expected"]


def test_golden_corpus_contains_no_secrets() -> None:
    leaks: list[str] = []
    for path in sorted(GOLDEN.rglob("*.json")):
        if detect(path.read_text(encoding="utf-8")):
            leaks.append(str(path.relative_to(GOLDEN)))

    assert not leaks, f"golden fixtures contain secrets: {leaks}"
