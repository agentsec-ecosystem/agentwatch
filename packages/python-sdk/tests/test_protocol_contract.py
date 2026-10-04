"""Published plumbing contract tests (M10 J1, #203).

Pins the store envelope, the tombstone envelope, and the daemon frame shape to
``agentwatch.protocol`` so the published reference docs cannot silently drift
from the runtime.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agentwatch import hook, protocol
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record() -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=START,
    )


def test_protocol_version_is_published() -> None:
    assert protocol.PROTOCOL_VERSION == "0.1.0"
    assert protocol.GENESIS_PREV_HASH == "0" * 64


def test_store_envelope_matches_the_published_contract(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())

    lines = store.path.read_text(encoding="utf-8").splitlines()

    assert json.loads(lines[0]) == {"format": protocol.STORE_FORMAT_VERSION}
    assert set(json.loads(lines[1])) == set(protocol.STORE_ENVELOPE_KEYS)


def test_tombstone_envelope_matches_the_published_contract(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())

    store.apply_retention(retention_days=1, now=datetime(2026, 6, 1, tzinfo=timezone.utc))

    tombstones = [
        json.loads(line)
        for line in store.path.read_text(encoding="utf-8").splitlines()
        if json.loads(line).get("tombstone")
    ]
    assert len(tombstones) == 1
    assert set(tombstones[0]) == set(protocol.TOMBSTONE_KEYS)


def test_daemon_frame_shapes_match_the_published_protocol() -> None:
    message = hook.build_message("pre", {"session_id": "s"})

    assert set(message) == set(protocol.FRAME_KEYS)
    assert message["harness"] == "claude-code"
    assert set(protocol.FRAME_PHASES) == {
        "pre",
        "post",
        "denied",
        "prompt",
        "session-start",
        "session-end",
        "hook-error",
        "event",
        "mcp",
    }


def test_mcp_phase_is_published() -> None:
    assert "mcp" in protocol.FRAME_PHASES
