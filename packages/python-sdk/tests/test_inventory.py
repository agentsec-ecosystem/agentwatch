"""Inventory aggregation tests (M9 R9, #72-#75/#177).

Shadow-agent and MCP-server inventory is derived from the local store only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agentwatch.cli.main import main
from agentwatch.inventory import build_inventory, inventory_to_json, render_inventory
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(
    *,
    session: str = "s1",
    identity: str = "research_crew",
    tool: str = "Bash",
    server: str | None = None,
    project: str | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity=identity),
        tool=ToolCall(name=tool, server=server),
        outcome=Outcome.OK,
        started_at=START,
        project=project,
    )


def _store(tmp_path: Path, records: list[AgentRecord]) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    for record in records:
        store.append(record)
    return store


def test_inventory_lists_agents_and_servers(tmp_path: Path) -> None:
    store = _store(
        tmp_path,
        [
            _record(identity="research_crew", tool="create_issue", server="github"),
            _record(identity="support_bot", tool="Bash"),
        ],
    )

    inv = build_inventory(store)

    assert [a.identity for a in inv.agents] == ["research_crew", "support_bot"]
    assert [s.server for s in inv.servers] == ["github"]


def test_inventory_aggregates_server_calls_tools_sessions(tmp_path: Path) -> None:
    store = _store(
        tmp_path,
        [
            _record(session="s1", tool="create_issue", server="github"),
            _record(session="s2", tool="create_issue", server="github"),
            _record(session="s2", tool="list_issues", server="github"),
        ],
    )

    (server,) = build_inventory(store).servers

    assert server.server == "github"
    assert server.tools == ("create_issue", "list_issues")
    assert server.calls == 3
    assert server.sessions == 2


def test_inventory_session_filter(tmp_path: Path) -> None:
    store = _store(
        tmp_path,
        [
            _record(session="s1", identity="research_crew", tool="create_issue", server="github"),
            _record(session="s2", identity="support_bot", tool="Bash"),
        ],
    )

    inv = build_inventory(store, session_id="s1")

    assert [a.identity for a in inv.agents] == ["research_crew"]
    assert [s.server for s in inv.servers] == ["github"]


def test_inventory_project_filter(tmp_path: Path) -> None:
    store = _store(
        tmp_path,
        [
            _record(session="s1", identity="a", project="/repo/a"),
            _record(session="s2", identity="b", project="/repo/b"),
        ],
    )

    inv = build_inventory(store, project="/repo/a")

    assert [a.identity for a in inv.agents] == ["a"]
    assert inv.agents[0].project == "/repo/a"


def test_render_and_json_shape(tmp_path: Path) -> None:
    store = _store(tmp_path, [_record(tool="create_issue", server="github")])
    inv = build_inventory(store)

    text = render_inventory(inv)
    assert "github" in text

    data = inventory_to_json(inv)
    assert data["agents"][0]["identity"] == "research_crew"
    assert data["servers"][0]["server"] == "github"
    assert data["servers"][0]["calls"] == 1


def test_cli_inventory_json(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir, [_record(tool="create_issue", server="github")])

    rc = main(["--set", f"store.path={store_dir}", "inventory", "--json"])

    assert rc == 0
