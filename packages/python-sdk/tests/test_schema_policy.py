"""Schema stewardship policy tests (M22 W5, #274)."""

from __future__ import annotations

import shutil
from pathlib import Path

from agentwatch.schema_policy import check_schema_policy

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA = REPO_ROOT / "schema"


def test_repository_schema_satisfies_the_policy() -> None:
    assert check_schema_policy(SCHEMA) == []


def test_enum_drift_without_changelog_fails(tmp_path: Path) -> None:
    target = tmp_path / "schema"
    shutil.copytree(SCHEMA, target)
    event_schema = target / "security-event.schema.json"
    text = event_schema.read_text(encoding="utf-8")
    # Introduce a new event type without touching the changelog.
    event_schema.write_text(
        text.replace('"agent-delegation"]', '"agent-delegation", "new-thing"]'),
        encoding="utf-8",
    )

    problems = check_schema_policy(target)

    assert any("enum does not match" in problem for problem in problems)


def test_missing_changelog_fails(tmp_path: Path) -> None:
    target = tmp_path / "schema"
    shutil.copytree(SCHEMA, target)
    (target / "CHANGELOG.md").unlink()

    problems = check_schema_policy(target)

    assert any("CHANGELOG.md" in problem for problem in problems)


def test_bad_id_url_fails(tmp_path: Path) -> None:
    target = tmp_path / "schema"
    shutil.copytree(SCHEMA, target)
    record_schema = target / "agent-record.schema.json"
    text = record_schema.read_text(encoding="utf-8")
    record_schema.write_text(
        text.replace('"$id": "https://', '"$id": "ftp://', 1), encoding="utf-8"
    )

    problems = check_schema_policy(target)

    assert any("$id must be a resolvable" in problem for problem in problems)
