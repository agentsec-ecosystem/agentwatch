"""OTel privacy-mode <-> content-capture mapping guard (M25 OTEL-2, #298).

Property: no content-bearing attribute escapes the active privacy mode on export.
The record->span mapping is metadata-only by construction, so a metadata-only store
can never leak content through the OTel path.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given
from hypothesis import strategies as st

from agentwatch.attrs import CONTENT_ATTRIBUTE_KEYS
from agentwatch.export import exported_content_keys, record_to_attributes
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(
    arguments: dict[str, object] | None,
    response: dict[str, object] | None,
    mode: RecordPrivacyMode | None,
) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(
            name="Bash", arguments=arguments, response=response, privacy_mode=mode
        ),
        outcome=Outcome.OK,
        started_at=AT,
    )


@given(st.text(max_size=200), st.text(max_size=200))
def test_no_content_attribute_escapes_regardless_of_mode(arguments: str, response: str) -> None:
    record = _record(
        {"cmd": arguments}, {"output": response}, RecordPrivacyMode.METADATA_ONLY
    )
    attributes = record_to_attributes(record, seq=0)

    assert exported_content_keys(attributes) == ()
    assert CONTENT_ATTRIBUTE_KEYS.isdisjoint(attributes)


def test_guard_detects_planted_content() -> None:
    attributes = {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.args": "secret"}
    assert exported_content_keys(attributes) == ("gen_ai.tool.args",)


def test_metadata_mapping_has_no_content_keys_for_any_mode() -> None:
    for mode in RecordPrivacyMode:
        attributes = record_to_attributes(_record({"x": "y"}, {"z": "w"}, mode), seq=1)
        assert exported_content_keys(attributes) == ()