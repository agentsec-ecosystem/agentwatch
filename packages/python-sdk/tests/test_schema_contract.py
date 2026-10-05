"""Fixtures + JSON-Schema contract tests for records/events (M2 #20/#117).

Two guarantees:
  * every valid fixture validates and every invalid fixture is rejected;
  * every model's ``to_dict()`` conforms to the published ``schema/*.json``
    (dev-only ``jsonschema``; the runtime validator stays dependency-free).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped]
import pytest
from referencing import Registry, Resource

from agentwatch.records import (
    CredentialClass,
    RecordPhase,
    RecordValidationError,
    SecurityEventType,
    validate_event,
    validate_record,
)

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES = TESTS_DIR / "fixtures"
SCHEMA_DIR = TESTS_DIR.parents[2] / "schema"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _files(*parts: str) -> list[Path]:
    return sorted(FIXTURES.joinpath(*parts).glob("*.json"))


RECORD_VALID = _files("records", "valid")
RECORD_INVALID = _files("records", "invalid")
EVENT_VALID = _files("events", "valid")
EVENT_INVALID = _files("events", "invalid")

_RECORD_SCHEMA = _load(SCHEMA_DIR / "agent-record.schema.json")
_EVENT_SCHEMA = _load(SCHEMA_DIR / "security-event.schema.json")
_SCHEMA_REGISTRY = Registry().with_resource(
    _EVENT_SCHEMA["$id"], Resource.from_contents(_EVENT_SCHEMA)
)
_RECORD_VALIDATOR = jsonschema.Draft202012Validator(_RECORD_SCHEMA, registry=_SCHEMA_REGISTRY)
_EVENT_VALIDATOR = jsonschema.Draft202012Validator(_EVENT_SCHEMA)


def test_fixture_directories_are_populated() -> None:
    # Guards against a silently-empty parametrization.
    assert RECORD_VALID and RECORD_INVALID and EVENT_VALID and EVENT_INVALID


def test_record_schema_enums_match_the_model() -> None:
    # W5: enum + model + JSON-Schema move together, pinned by a contract test.
    assert set(_RECORD_SCHEMA["properties"]["record_phase"]["enum"]) == (
        {phase.value for phase in RecordPhase} | {None}
    )
    agent_props = _RECORD_SCHEMA["properties"]["agent"]["properties"]
    assert set(agent_props["credential_class"]["enum"]) == (
        {credential.value for credential in CredentialClass} | {None}
    )


def test_event_schema_enum_matches_the_model() -> None:
    assert set(_EVENT_SCHEMA["properties"]["type"]["enum"]) == {
        member.value for member in SecurityEventType
    }


@pytest.mark.parametrize("path", RECORD_VALID, ids=lambda p: p.name)
def test_valid_record_fixtures_validate_and_match_schema(path: Path) -> None:
    record = validate_record(_load(path))
    _RECORD_VALIDATOR.validate(record.to_dict())


@pytest.mark.parametrize("path", RECORD_INVALID, ids=lambda p: p.name)
def test_invalid_record_fixtures_are_rejected(path: Path) -> None:
    with pytest.raises(RecordValidationError):
        validate_record(_load(path))


@pytest.mark.parametrize("path", EVENT_VALID, ids=lambda p: p.name)
def test_valid_event_fixtures_validate_and_match_schema(path: Path) -> None:
    event = validate_event(_load(path))
    _EVENT_VALIDATOR.validate(event.to_dict())


@pytest.mark.parametrize("path", EVENT_INVALID, ids=lambda p: p.name)
def test_invalid_event_fixtures_are_rejected(path: Path) -> None:
    with pytest.raises(RecordValidationError):
        validate_event(_load(path))
