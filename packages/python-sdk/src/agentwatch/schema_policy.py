"""Schema stewardship policy check (M22 W5, PRD 39).

`schema/` is machine-readable; this makes the policy around it enforceable. A
schema change must move together with its changelog and the Python vocabulary, or
the policy check fails. It also asserts resolvable ``$id`` URLs so a consumer can
find the contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from agentwatch.records import EVENT_VERSION, SCHEMA_VERSION, SecurityEventType

SCHEMA_CHANGELOG = "CHANGELOG.md"
SECURITY_EVENT_SCHEMA = "security-event.schema.json"


def _load(path: Path) -> dict[str, object]:
    return cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))


def check_schema_policy(schema_dir: Path | str) -> list[str]:
    """Return a list of policy violations (empty means the policy holds)."""
    root = Path(schema_dir)
    problems: list[str] = []

    for path in sorted(root.glob("*.schema.json")):
        try:
            document = _load(path)
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{path.name}: cannot read ({exc})")
            continue
        identifier = document.get("$id")
        if not isinstance(identifier, str) or not identifier.startswith("http"):
            problems.append(f"{path.name}: $id must be a resolvable http(s) URL")

    changelog = root / SCHEMA_CHANGELOG
    if not changelog.exists():
        problems.append(f"{SCHEMA_CHANGELOG}: missing (a schema change needs a changelog entry)")
    else:
        text = changelog.read_text(encoding="utf-8")
        if SCHEMA_VERSION not in text:
            problems.append(f"{SCHEMA_CHANGELOG}: no entry for schema version {SCHEMA_VERSION}")

    event_schema = root / SECURITY_EVENT_SCHEMA
    if event_schema.exists():
        document = _load(event_schema)
        properties = document.get("properties")
        if isinstance(properties, dict):
            type_prop = properties.get("type")
            if isinstance(type_prop, dict):
                enum = type_prop.get("enum")
                if isinstance(enum, list):
                    declared = {str(item) for item in enum}
                    actual = {member.value for member in SecurityEventType}
                    if declared != actual:
                        problems.append(
                            f"{SECURITY_EVENT_SCHEMA}: enum does not match "
                            f"records.SecurityEventType "
                            f"(only-in-schema={sorted(declared - actual)}, "
                            f"only-in-code={sorted(actual - declared)})"
                        )
            version_prop = properties.get("event_version")
            if isinstance(version_prop, dict) and version_prop.get("const") != EVENT_VERSION:
                problems.append(
                    f"{SECURITY_EVENT_SCHEMA}: event_version const "
                    f"{version_prop.get('const')!r} != {EVENT_VERSION!r}"
                )

    return problems


__all__ = ["SCHEMA_CHANGELOG", "SECURITY_EVENT_SCHEMA", "check_schema_policy"]
