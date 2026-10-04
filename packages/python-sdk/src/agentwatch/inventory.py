"""Shadow-agent + MCP-server inventory from the local store (M9 R9, #72-#75/#177).

Read-only and local: aggregates the agents that have been recorded and the MCP
servers seen in ``tool.server`` (populated from ``mcp__<server>__<tool>`` names).
Metadata only — no arguments, no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agentwatch.records import AgentRecord
from agentwatch.store import RecordStore


@dataclass(frozen=True)
class AgentSummary:
    """One recorded agent identity and what it did."""

    identity: str
    name: str | None
    version: str | None
    project: str | None
    sessions: int
    records: int
    last_seen: datetime


@dataclass(frozen=True)
class ServerSummary:
    """One MCP server seen in the store."""

    server: str
    tools: tuple[str, ...]
    calls: int
    sessions: int
    last_seen: datetime


@dataclass(frozen=True)
class Inventory:
    """The full local readout."""

    agents: tuple[AgentSummary, ...]
    servers: tuple[ServerSummary, ...]


@dataclass
class _AgentAcc:
    name: str | None
    version: str | None
    project: str | None
    sessions: set[str] = field(default_factory=set)
    records: int = 0
    last_seen: datetime | None = None


@dataclass
class _ServerAcc:
    tools: set[str] = field(default_factory=set)
    calls: int = 0
    sessions: set[str] = field(default_factory=set)
    last_seen: datetime | None = None


def _selected(record: AgentRecord, session_id: str | None, project: str | None) -> bool:
    return (session_id is None or record.session_id == session_id) and (
        project is None or record.project == project
    )


def _newer(current: datetime | None, candidate: datetime) -> datetime:
    return candidate if current is None or candidate > current else current


def build_inventory(
    store: RecordStore, *, session_id: str | None = None, project: str | None = None
) -> Inventory:
    """Aggregate agents and MCP servers from the store (optionally filtered)."""
    agents: dict[str, _AgentAcc] = {}
    servers: dict[str, _ServerAcc] = {}

    for record in store.records():
        if not _selected(record, session_id, project):
            continue

        agent = agents.get(record.agent.identity)
        if agent is None:
            agent = _AgentAcc(
                name=record.agent.name,
                version=record.agent.version,
                project=record.project,
            )
            agents[record.agent.identity] = agent
        agent.sessions.add(record.session_id)
        agent.records += 1
        agent.last_seen = _newer(agent.last_seen, record.started_at)

        server = record.tool.server
        if server is not None:
            entry = servers.get(server)
            if entry is None:
                entry = _ServerAcc()
                servers[server] = entry
            entry.tools.add(record.tool.name)
            entry.calls += 1
            entry.sessions.add(record.session_id)
            entry.last_seen = _newer(entry.last_seen, record.started_at)

    agent_summaries = tuple(
        AgentSummary(
            identity=key,
            name=acc.name,
            version=acc.version,
            project=acc.project,
            sessions=len(acc.sessions),
            records=acc.records,
            last_seen=acc.last_seen or datetime.min,
        )
        for key, acc in sorted(agents.items())
    )
    server_summaries = tuple(
        ServerSummary(
            server=key,
            tools=tuple(sorted(acc.tools)),
            calls=acc.calls,
            sessions=len(acc.sessions),
            last_seen=acc.last_seen or datetime.min,
        )
        for key, acc in sorted(servers.items())
    )
    return Inventory(agents=agent_summaries, servers=server_summaries)


def render_inventory(inventory: Inventory) -> str:
    """Human-readable inventory table."""
    lines = ["AGENT\tNAME\tVERSION\tPROJECT\tSESSIONS\tRECORDS\tLAST SEEN"]
    for agent in inventory.agents:
        lines.append(
            f"{agent.identity}\t{agent.name or '-'}\t{agent.version or '-'}\t"
            f"{agent.project or '-'}\t{agent.sessions}\t{agent.records}\t"
            f"{agent.last_seen.isoformat()}"
        )
    lines.append("")
    lines.append("SERVER\tTOOLS\tCALLS\tSESSIONS\tLAST SEEN")
    for server in inventory.servers:
        lines.append(
            f"{server.server}\t{','.join(server.tools)}\t{server.calls}\t"
            f"{server.sessions}\t{server.last_seen.isoformat()}"
        )
    return "\n".join(lines)


def inventory_to_json(inventory: Inventory) -> dict[str, Any]:
    """Stable JSON shape for scripting."""
    return {
        "agents": [
            {
                "identity": agent.identity,
                "name": agent.name,
                "version": agent.version,
                "project": agent.project,
                "sessions": agent.sessions,
                "records": agent.records,
                "last_seen": agent.last_seen.isoformat(),
            }
            for agent in inventory.agents
        ],
        "servers": [
            {
                "server": server.server,
                "tools": list(server.tools),
                "calls": server.calls,
                "sessions": server.sessions,
                "last_seen": server.last_seen.isoformat(),
            }
            for server in inventory.servers
        ],
    }
