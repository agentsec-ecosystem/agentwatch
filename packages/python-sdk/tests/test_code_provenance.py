"""PRV-3 content-free range+hash capture tests (M30 #464, PRD 53).

The minimum for line attribution is the affected line range plus a keyed content
hash — never the content. These tests are the property + attack pack behind the
"no content/diff under metadata-only" guarantee (ADR-0033).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agentwatch.provenance import (
    AGENTWATCH_ATTRIBUTION_KEY,
    CONTENT_KEYS,
    RANGE_CAPTURE_VERSION,
    LineRange,
    capture_ranges,
    is_content_free,
    range_facts_from_record,
    to_attribution_arguments,
)
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)

SECRET = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
CONTENT = "def add(a, b):\n    return a + b\n"


def _edit_arguments() -> dict[str, object]:
    return {
        "file_path": "/repo/app.py",
        "start_line": 3,
        "end_line": 5,
        "new_string": CONTENT,
    }


def test_capture_extracts_range_and_keyed_hash_without_content() -> None:
    capture = capture_ranges(_edit_arguments(), tool_name="Edit")

    assert capture.path == "/repo/app.py"
    assert capture.ranges == (LineRange(3, 5),)
    assert len(capture.hashes) == 1
    assert capture.hashes[0].startswith("hmac-sha256:")
    assert capture.confidence == "exact"
    assert capture.fallback is None
    assert capture.version == RANGE_CAPTURE_VERSION
    assert CONTENT not in json.dumps(capture.to_dict())


def test_capture_parses_line_range_string() -> None:
    capture = capture_ranges(
        {"file_path": "app.py", "line_range": "10-12", "new_text": CONTENT},
        tool_name="str_replace",
    )
    assert capture.ranges == (LineRange(10, 12),)
    assert capture.confidence == "exact"


def test_capture_falls_back_to_file_level_heuristic() -> None:
    capture = capture_ranges({"file_path": "app.py", "content": CONTENT}, tool_name="Write")

    assert capture.ranges == ()
    assert capture.fallback == "file-level"
    assert capture.confidence == "heuristic"
    assert capture.hashes  # a file-level keyed hash still exists
    assert CONTENT not in json.dumps(capture.to_dict())


def test_capture_without_path_is_not_attributable() -> None:
    capture = capture_ranges({"content": CONTENT}, tool_name="Write")
    assert capture.path is None
    assert capture.ranges == ()
    assert capture.fallback == "file-level"


def test_line_range_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError):
        LineRange(0, 1)
    with pytest.raises(ValueError):
        LineRange(5, 4)


def test_capture_is_content_free_under_metadata_only() -> None:
    capture = capture_ranges(_edit_arguments(), tool_name="Edit", privacy_mode="metadata-only")
    payload = capture.to_dict()

    # ranges + hashes exist under metadata-only; no content or diff does.
    assert payload["ranges"] == [{"start": 3, "end": 5}]
    assert payload["hashes"]
    assert is_content_free(payload)
    assert not any(key in payload for key in CONTENT_KEYS)


_ATTACK_PACK = (
    CONTENT,
    SECRET,
    "-----BEGIN RSA PRIVATE KEY-----\nMIIE\n-----END RSA PRIVATE KEY-----\n",
    "password=hunter2",
    "diff --git a/x b/x\n+secret line\n",
)


@pytest.mark.parametrize("attack", _ATTACK_PACK)
def test_attack_pack_never_leaks_content(attack: str) -> None:
    capture = capture_ranges(
        {
            "file_path": "app.py",
            "start_line": 1,
            "end_line": 2,
            "old_string": attack,
            "new_string": attack,
        },
        tool_name="Edit",
        privacy_mode="metadata-only",
    )
    serialized = json.dumps(capture.to_dict(), sort_keys=True)
    assert attack not in serialized
    assert SECRET not in serialized
    assert is_content_free(capture.to_dict())


@given(st.text())
def test_property_capture_never_contains_the_content(secret: str) -> None:
    capture = capture_ranges({"file_path": "f.py", "content": secret}, tool_name="Write")
    # The only string the capture stores for content is a keyed hash; it can never
    # be the content itself.
    assert capture.hashes
    assert all(re.fullmatch(r"hmac-sha256:[0-9a-f]{64}", item) for item in capture.hashes)
    assert is_content_free(capture.to_dict())


def test_range_facts_roundtrip_under_metadata_only() -> None:
    capture = capture_ranges(_edit_arguments(), tool_name="Edit")
    record = AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="agent-1"),
        tool=ToolCall(
            name="Edit",
            arguments=to_attribution_arguments(capture),
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
        outcome=Outcome.OK,
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    restored = range_facts_from_record(record)

    assert restored is not None
    assert restored.ranges == (LineRange(3, 5),)
    assert restored.hashes == capture.hashes
    assert AGENTWATCH_ATTRIBUTION_KEY in (record.tool.arguments or {})
    assert CONTENT not in json.dumps(record.to_dict())


def test_range_facts_absent_without_reserved_arguments() -> None:
    record = AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="agent-1"),
        tool=ToolCall(name="Bash", arguments={"command": "ls"}),
        outcome=Outcome.OK,
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert range_facts_from_record(record) is None
