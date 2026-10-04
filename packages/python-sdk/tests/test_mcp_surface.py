"""MCP tool-surface snapshot + drift tests (M20 S4, #264)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.mcp_surface import (
    MCP_SURFACE_TOOL,
    detect_surface_changes,
    record_mcp_surface,
    surface_digest,
    survey,
)
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    SecurityEventType,
    StepType,
    ToolCall,
)
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _tool(session: str, server: str, name: str, minute: int) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=name, server=server),
        outcome=Outcome.OK,
        started_at=START + timedelta(minutes=minute),
        step_type=StepType.ACT,
    )


def _carrier(session: str, server: str, observed: list[str], enumerated: list[str]) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agentwatch"),
        tool=ToolCall(
            name=MCP_SURFACE_TOOL,
            server=server,
            arguments={"server": server, "observed": observed, "enumerated": enumerated},
        ),
        outcome=Outcome.OK,
        started_at=START,
        step_type=StepType.OBSERVE,
    )


def test_surface_digest_is_order_independent() -> None:
    assert surface_digest(["b", "a"]) == surface_digest(["a", "b", "a"])


def test_survey_keeps_observed_and_enumerated_distinct() -> None:
    records = [
        _tool("s1", "github", "search", 0),
        _carrier("s1", "github", ["search"], ["search", "create_issue"]),
    ]

    states = survey(records)

    assert len(states) == 1
    assert states[0].observed == ("search",)
    assert states[0].enumerated == ("create_issue", "search")


def test_change_between_two_sessions_emits_one() -> None:
    records = [
        _tool("s1", "github", "search", 0),
        _tool("s2", "github", "search", 10),
        _tool("s2", "github", "create_issue", 11),
    ]

    changes = detect_surface_changes(records)

    assert len(changes) == 1
    change = changes[0]
    assert change.server == "github"
    assert change.session_id == "s2"
    assert change.prev_session_id == "s1"
    assert change.added == ("create_issue",)
    assert change.removed == ()
    assert change.prev_digest and change.digest
    assert change.prev_digest != change.digest


def test_unchanged_server_emits_none() -> None:
    records = [
        _tool("s1", "github", "search", 0),
        _tool("s2", "github", "search", 10),
    ]
    assert detect_surface_changes(records) == []


def test_first_seen_server_emits_none() -> None:
    records = [_tool("s1", "github", "search", 0)]
    assert detect_surface_changes(records) == []


def test_record_mcp_surface_appends_carrier_and_event(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_tool("s1", "github", "search", 0))
    store.append(_tool("s2", "github", "search", 10))
    store.append(_tool("s2", "github", "create_issue", 11))

    changes = record_mcp_surface(store, "s2")

    assert len(changes) == 1
    carriers = [r for r in store.records() if r.tool.name == MCP_SURFACE_TOOL]
    events = [
        r
        for r in store.records()
        if r.security_event is not None
        and r.security_event.type is SecurityEventType.TOOL_SURFACE_CHANGED
    ]
    assert any(c.session_id == "s2" for c in carriers)
    assert len(events) == 1
    assert events[0].security_event is not None
    assert events[0].security_event.evidence is not None
    assert events[0].security_event.evidence["added"] == ["create_issue"]


def test_cli_inventory_snapshot_and_diff(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    store.append(_tool("s1", "github", "search", 0))
    store.append(_tool("s2", "github", "create_issue", 10))

    rc = main(["--set", f"store.path={store_dir}", "inventory", "--snapshot", "--json"])
    assert rc == 0
    snap = json.loads(capsys.readouterr().out)
    assert {state["server"] for state in snap} == {"github"}

    rc = main(["--set", f"store.path={store_dir}", "inventory", "--diff", "--json"])
    assert rc == 0
    diff = json.loads(capsys.readouterr().out)
    assert len(diff) == 1
    assert diff[0]["added"] == ["create_issue"]
