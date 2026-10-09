"""Investigation skill + versioned CLI JSON schemas (M30 AGI-2, #468).

A shipped skill teaches coding agents the investigation workflow over the CLI
JSON contract; the contract lives in a versioned ``schema/cli/`` directory with
its own changelog, guarded so a schema change must move with the changelog. A
scripted agent reaches documented answers on the demo store.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.cli_schema import (
    CLI_SCHEMA_VERSION,
    READ_COMMANDS,
    check_cli_schemas,
    registered_schemas,
    validate,
)
from agentwatch.demo import run_demo
from agentwatch.store import RecordStore

REPO = Path(__file__).resolve().parents[3]
SKILL_DIR = REPO / "docs" / "skills" / "investigation"
SKILL = SKILL_DIR / "SKILL.md"
SCHEMA_CLI = REPO / "schema" / "cli"


def _copy_schema_dir(tmp_path: Path) -> Path:
    target = tmp_path / "schema" / "cli"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SCHEMA_CLI, target)
    return tmp_path


# --- versioned schemas + changelog guard --------------------------------------


def test_every_registered_read_command_has_a_versioned_schema() -> None:
    assert check_cli_schemas(REPO) == []
    assert set(registered_schemas(REPO)) == set(READ_COMMANDS)


def test_cli_schema_dir_ships_its_own_changelog_and_readme() -> None:
    changelog = SCHEMA_CLI / "CHANGELOG.md"
    readme = SCHEMA_CLI / "README.md"
    assert changelog.exists()
    assert readme.exists()
    assert CLI_SCHEMA_VERSION in changelog.read_text(encoding="utf-8")
    assert f"v{CLI_SCHEMA_VERSION}" in readme.read_text(encoding="utf-8")


def test_changelog_guard_fails_when_the_version_is_not_named(tmp_path: Path) -> None:
    root = _copy_schema_dir(tmp_path)
    changelog = root / "schema" / "cli" / "CHANGELOG.md"
    changelog.write_text("# CLI schema changelog\n\nnothing here\n", encoding="utf-8")

    problems = check_cli_schemas(root)

    assert any("CHANGELOG" in problem for problem in problems)


def test_changelog_guard_fails_for_an_unregistered_schema_file(tmp_path: Path) -> None:
    root = _copy_schema_dir(tmp_path)
    stray = root / "schema" / "cli" / f"v{CLI_SCHEMA_VERSION}" / "stray.schema.json"
    stray.write_text(json.dumps({"$id": "https://x/stray", "type": "object"}), encoding="utf-8")

    problems = check_cli_schemas(root)

    assert any("stray" in problem for problem in problems)


def test_validate_rejects_a_wrong_top_level_type() -> None:
    assert validate("impact", []) != []
    assert validate("search", {"not": "a record"}) != []
    assert validate("impact", {"session_id": "demo"}) == []


# --- the shipped skill ---------------------------------------------------------


def test_skill_teaches_the_investigation_workflow() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert SKILL.exists()
    for step in ("search", "replay", "impact", "evidence"):
        assert step in text
    assert CLI_SCHEMA_VERSION in text
    assert "untrusted" in text.lower()


# --- a scripted agent reaches documented answers on the demo store -------------


def test_scripted_agent_reaches_documented_answers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    run_demo(store, cwd=str(tmp_path))
    base = ["--set", f"store.path={store_dir}"]

    assert main([*base, "sessions"]) == 0
    sessions_out = capsys.readouterr().out
    assert "demo" in sessions_out

    assert main([*base, "search", "--session", "demo", "--json"]) == 0
    found = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.strip()
    ]
    assert len(found) == 6

    assert main([*base, "replay", "demo", "--json"]) == 0
    replay = json.loads(capsys.readouterr().out)
    assert len(replay) == 6
    assert all("record" in item for item in replay)

    assert main([*base, "impact", "demo", "--json"]) == 0
    impact = json.loads(capsys.readouterr().out)
    assert impact["session_id"] == "demo"
    assert impact["records"] == 6
    assert impact["denials"]
