"""Versioned CLI JSON contract + changelog guard (M30 AGI-2, #468).

Agent adoption needs a stable machine contract. The read/investigation commands'
``--json`` output is published as versioned JSON Schemas under
``schema/cli/v<version>/`` with their own changelog, guarded exactly like the
record schema: a schema file must move with a changelog entry, a command without
a schema fails, and a schema without a command fails.

This module is the single source of truth for the registered read commands and
the guard; the skill (``docs/skills/investigation/SKILL.md``) teaches agents to
drive those commands.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

#: Current published version of the CLI JSON contract.
CLI_SCHEMA_VERSION = "0.1.0"

#: Directory (relative to the repo root) that holds the versioned CLI contract.
SCHEMA_CLI_DIR = Path("schema") / "cli"

CLI_SCHEMA_CHANGELOG = "CHANGELOG.md"
CLI_SCHEMA_README = "README.md"

#: Read/investigation command -> the shape of one ``--json`` payload at the top level.
#: ``ndjson`` is one JSON object per line (a record stream).
OUTPUT_KIND: dict[str, str] = {
    "search": "ndjson",
    "replay": "array",
    "impact": "object",
    "blame": "object",
    "coverage": "object",
    "cost": "object",
    "oversight": "object",
    "inventory": "object",
    "diff": "object",
    "trace": "object",
    "tree": "object",
    "flow": "array",
    "secrets": "array",
}

#: The registered read commands, in stable order.
READ_COMMANDS: tuple[str, ...] = tuple(OUTPUT_KIND)

# JSON Schema ``type`` for each output kind (NDJSON is a stream of objects).
_JSON_TYPE = {"object": "object", "array": "array", "ndjson": "object"}

# Identity fields every record line must carry (mirrors search.schema.json).
_RECORD_REQUIRED = ("session_id", "tool", "outcome", "started_at")


def version_dir(repo_root: Path | str) -> Path:
    return Path(repo_root) / SCHEMA_CLI_DIR / f"v{CLI_SCHEMA_VERSION}"


def schema_path(repo_root: Path | str, command: str) -> Path:
    return version_dir(repo_root) / f"{command}.schema.json"


def registered_schemas(repo_root: Path | str) -> dict[str, Path]:
    """The schema file for each registered command that exists on disk."""
    result: dict[str, Path] = {}
    for command in READ_COMMANDS:
        path = schema_path(repo_root, command)
        if path.exists():
            result[command] = path
    return result


def _load(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def check_cli_schemas(repo_root: Path | str) -> list[str]:
    """Return the contract violations (empty means the contract holds)."""
    root = Path(repo_root)
    cli = root / SCHEMA_CLI_DIR
    problems: list[str] = []

    changelog = cli / CLI_SCHEMA_CHANGELOG
    if not changelog.exists():
        problems.append(f"{cli}/{CLI_SCHEMA_CHANGELOG}: missing (a schema needs a changelog)")
    elif CLI_SCHEMA_VERSION not in changelog.read_text(encoding="utf-8"):
        problems.append(
            f"{CLI_SCHEMA_CHANGELOG}: does not name the current CLI schema version "
            f"{CLI_SCHEMA_VERSION}"
        )

    if not (cli / CLI_SCHEMA_README).exists():
        problems.append(f"{cli}/{CLI_SCHEMA_README}: missing")

    directory = version_dir(root)
    if not directory.is_dir():
        problems.append(f"{directory}: missing versioned schema directory")
        return problems

    for command in READ_COMMANDS:
        path = schema_path(root, command)
        if not path.exists():
            problems.append(f"{path}: missing schema for read command {command!r}")
            continue
        try:
            document = _load(path)
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{path.name}: cannot read ({exc})")
            continue
        identifier = document.get("$id")
        if not isinstance(identifier, str) or not identifier.startswith("http"):
            problems.append(f"{path.name}: $id must be a resolvable http(s) URL")
        if not document.get("title"):
            problems.append(f"{path.name}: missing title")
        expected = _JSON_TYPE[OUTPUT_KIND[command]]
        if document.get("type") != expected:
            problems.append(
                f"{path.name}: type must be {expected!r} for a {OUTPUT_KIND[command]} output"
            )

    for path in sorted(directory.glob("*.schema.json")):
        command = path.name[: -len(".schema.json")]
        if command not in READ_COMMANDS:
            problems.append(f"{path.name}: schema for unregistered read command {command!r}")

    return problems


def validate(command: str, payload: Any) -> list[str]:
    """Light structural validation of one ``--json`` payload against its kind.

    No third-party validator is introduced (NFR-5); this checks the top-level
    shape that the contract promises.
    """
    kind = OUTPUT_KIND.get(command)
    if kind is None:
        return [f"unknown read command {command!r}"]
    expected = _JSON_TYPE[kind]
    if isinstance(payload, list):
        actual = "array"
    elif isinstance(payload, dict):
        actual = "object"
    else:
        actual = "other"
    if actual != expected:
        return [f"{command}: expected top-level {expected} ({kind}), got {actual}"]
    if actual == "other":
        return [f"{command}: payload must be a JSON {expected}"]
    if kind == "ndjson":
        missing = [key for key in _RECORD_REQUIRED if key not in payload]
        if missing:
            return [f"{command}: record line missing {', '.join(missing)}"]
    return []


__all__ = [
    "CLI_SCHEMA_CHANGELOG",
    "CLI_SCHEMA_README",
    "CLI_SCHEMA_VERSION",
    "OUTPUT_KIND",
    "READ_COMMANDS",
    "SCHEMA_CLI_DIR",
    "check_cli_schemas",
    "registered_schemas",
    "schema_path",
    "validate",
    "version_dir",
]
