"""IDN-4 — credential-hygiene observation (M28, #363; PRD 44 §IDN-4).

The record layer already carries ``credential_class`` (IDN-1); this proves the
class is exported as a span attribute so the analytics detector can flag
``ambient/shared`` credentials — NIST's pre-Q4-2026 audit ask — without
inferring anything the record did not state.
"""

from __future__ import annotations

from datetime import datetime, timezone

from agentwatch.attrs import AGENTWATCH_CREDENTIAL_CLASS
from agentwatch.export import record_to_attributes
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    CredentialClass,
    Outcome,
    ToolCall,
)

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(credential: CredentialClass | None) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="agent", name="agent", credential_class=credential),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=AT,
    )


def test_credential_class_attribute_key_is_stable() -> None:
    assert AGENTWATCH_CREDENTIAL_CLASS == "agentwatch.credential_class"


def test_ambient_shared_credential_is_exported() -> None:
    attributes = record_to_attributes(_record(CredentialClass.AMBIENT_SHARED), seq=1)

    assert attributes[AGENTWATCH_CREDENTIAL_CLASS] == "ambient/shared"


def test_known_credential_class_is_exported() -> None:
    attributes = record_to_attributes(_record(CredentialClass.API_KEY), seq=1)

    assert attributes[AGENTWATCH_CREDENTIAL_CLASS] == "api-key"


def test_absent_credential_class_is_not_invented() -> None:
    attributes = record_to_attributes(_record(None), seq=1)

    assert AGENTWATCH_CREDENTIAL_CLASS not in attributes
