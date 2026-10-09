"""New security-event vocabulary + mappings tests (M29 EXT-3, #453; PRD 48).

`recorder-config-changed` (DEP-2) and `mode-transition` (APV-2/WS-A) become
first-class, versioned security events with OCSF/CloudEvents mappings and
fixtures. `capability-changed` is added to the vocabulary as a **forward-compatible
placeholder** for M30 CAP-2 (not built) — its dependency is marked, not hidden.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agentwatch.ocsf import MAPPING_TABLE, ocsf_target, to_cloudevents, to_ocsf
from agentwatch.records import (
    SecurityEvent,
    SecurityEventType,
    validate_event,
)
from agentwatch.schema_policy import check_schema_policy

REPO = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO / "schema"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "events" / "valid"
AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

NEW_TYPES = (
    SecurityEventType.RECORDER_CONFIG_CHANGED,
    SecurityEventType.MODE_TRANSITION,
    SecurityEventType.CAPABILITY_CHANGED,
)


def test_new_event_types_are_in_the_vocabulary() -> None:
    assert SecurityEventType.RECORDER_CONFIG_CHANGED.value == "recorder-config-changed"
    assert SecurityEventType.MODE_TRANSITION.value == "mode-transition"
    assert SecurityEventType.CAPABILITY_CHANGED.value == "capability-changed"


def test_schema_enum_matches_the_code_vocabulary() -> None:
    document = json.loads((SCHEMA_DIR / "security-event.schema.json").read_text(encoding="utf-8"))
    declared = set(document["properties"]["type"]["enum"])
    assert declared == {member.value for member in SecurityEventType}


def test_schema_policy_passes() -> None:
    assert check_schema_policy(SCHEMA_DIR) == []


def test_every_new_type_has_ocsf_and_cloudevents_mappings() -> None:
    for member in NEW_TYPES:
        assert member.value in MAPPING_TABLE
        assert ocsf_target(member.value) is not None
        event = SecurityEvent(type=member, emitted_at=AT, emitter="agentwatch")
        ocsf = to_ocsf(event)
        assert ocsf["class_uid"] >= 2000
        envelope = to_cloudevents(event)
        assert envelope["type"] == f"io.agentwatch.security-event.{member.value}"


def test_mode_transition_constructs_and_validates() -> None:
    event = SecurityEvent(
        type=SecurityEventType.MODE_TRANSITION,
        emitted_at=AT,
        emitter="agentwatch",
        reason="default -> bypass",
        evidence={"from": "default", "to": "bypass", "source": "permission-mode"},
    )

    validated = validate_event(event.to_dict())

    assert validated.type is SecurityEventType.MODE_TRANSITION
    assert validated.evidence == {
        "from": "default",
        "to": "bypass",
        "source": "permission-mode",
    }


def test_recorder_config_changed_carries_digests_only() -> None:
    event = SecurityEvent(
        type=SecurityEventType.RECORDER_CONFIG_CHANGED,
        emitted_at=AT,
        emitter="agentwatch",
        reason="effective hook config digest changed",
        evidence={"old_digest": "0123456789abcdef", "new_digest": "fedcba9876543210"},
    )

    data = event.to_dict()
    validate_event(data)
    assert "digest" in json.dumps(data["evidence"])
    # No raw config value is ever present.
    assert "secret" not in json.dumps(data).lower()


def test_capability_changed_is_a_documented_forward_placeholder() -> None:
    # The mapping exists so consumers stay stable, but the event originates in
    # M30 CAP-2 (not built); the design doc must mark the dependency.
    assert ocsf_target("capability-changed") is not None
    spec = (REPO / "docs" / "reference" / "record-format-spec.md").read_text(encoding="utf-8")
    assert "capability-changed" in spec
    assert "CAP-2" in spec


def test_new_types_are_in_the_incident_taxonomy() -> None:
    from agentwatch.incident_taxonomy import AIR_BY_EVENT, GMF_BY_EVENT

    for member in NEW_TYPES:
        assert member.value in AIR_BY_EVENT
        assert member.value in GMF_BY_EVENT


def test_new_event_fixtures_validate() -> None:
    for name in ("mode-transition.json", "recorder-config-changed.json", "capability-changed.json"):
        path = FIXTURES / name
        assert path.is_file(), name
        event = validate_event(json.loads(path.read_text(encoding="utf-8")))
        assert event.type.value in {member.value for member in NEW_TYPES}
