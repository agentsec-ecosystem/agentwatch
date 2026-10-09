"""Incident-registry taxonomy + annotate incident tags (M27 COR-2 #345).

Findings/events map to the **AIR** schema fields (architecture/mechanism/control/
agency/outcome) and the incident database **GMF** taxonomy — every event type has
a correspondent or an explicit ``None`` (never a silent omission). ``annotate``
gains optional incident tags, stored metadata-only and secret-scrubbed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.annotate import annotate_session
from agentwatch.incident_taxonomy import (
    AIR_BY_EVENT,
    GMF_BY_EVENT,
    air_mapping,
    gmf_mapping,
)
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    SecurityEventType,
    ToolCall,
)
from agentwatch.store import RecordStore

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def test_every_event_has_an_explicit_air_and_gmf_entry() -> None:
    for event_type in SecurityEventType:
        assert event_type.value in AIR_BY_EVENT
        assert event_type.value in GMF_BY_EVENT


def test_air_mapping_carries_the_documented_fields() -> None:
    mapping = air_mapping(SecurityEventType.DENIED)
    assert mapping is not None
    assert set(mapping) == {"architecture", "mechanism", "control", "agency", "outcome"}


def test_gmf_mapping_is_explicit_when_unpinned() -> None:
    # GMF values are explicit ``None`` where our alignment is not yet pinned —
    # never an accidental omission.
    assert gmf_mapping(SecurityEventType.TOOL_SURFACE_CHANGED) is None
    assert gmf_mapping(SecurityEventType.DENIED) is not None


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        AgentRecord(
            session_id="s1",
            agent=AgentIdentity(identity="agent"),
            tool=ToolCall(name="Bash"),
            outcome=Outcome.OK,
            started_at=AT,
        )
    )
    return store


def test_annotate_stores_incident_tags_metadata_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    annotate_session(store, "s1", "reviewed", incident_tags=["AIR:denied", "GMF:misuse"])

    note = next(r for r in store.records() if r.tool.name == "operator-note")
    assert note.tool.arguments is not None
    assert note.tool.arguments["incident_tags"] == ["AIR:denied", "GMF:misuse"]
    assert note.tool.privacy_mode is RecordPrivacyMode.METADATA_ONLY


def test_incident_tag_secret_is_masked(tmp_path: Path) -> None:
    store = _store(tmp_path)
    annotate_session(store, "s1", "reviewed", incident_tags=["token=sk-abcdefgh"])

    note = next(r for r in store.records() if r.tool.name == "operator-note")
    assert note.tool.arguments is not None
    assert "sk-abcdefgh" not in str(note.tool.arguments)


def test_incident_tags_are_capped_and_validated(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(ValueError):
        annotate_session(store, "s1", "reviewed", incident_tags=[" " * 3])
