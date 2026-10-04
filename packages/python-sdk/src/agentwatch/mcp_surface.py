"""MCP tool-surface snapshot + drift (M20 S4, PRD 36).

A rug-pull is detectable with nothing but a record: **the tool surface a server
presented changed between sessions.** agentwatch already attributes
``mcp__<server>__<tool>`` into ``tool.server``/``tool.name``; this module keeps
the time dimension.

Per session we record one ``mcp-surface`` carrier per server: the **observed**
tool set (from usage) and, when available from ``tools/list``, the **enumerated**
set — two distinct fields, never merged. A digest of the observed set is
compared across sessions; a change emits the ``tool-surface-changed`` security
event with ``added``/``removed`` and both digests. This is observation only — a
surface change is not a malware verdict.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    SecurityEvent,
    SecurityEventType,
    StepType,
    ToolCall,
)
from agentwatch.store import MARKER_PRODUCER, RecordStore

MCP_SURFACE_TOOL = "mcp-surface"
SURFACE_EVENT_TOOL = "tool-surface-changed"


def surface_digest(tools: Iterable[str]) -> str:
    """A stable digest of a tool set (order- and duplicate-independent)."""
    canonical = "\n".join(sorted(set(tools)))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class SurfaceState:
    """One server's surface as seen in one session."""

    server: str
    session_id: str
    observed: tuple[str, ...]
    enumerated: tuple[str, ...]
    digest: str
    at: datetime

    @property
    def observed_digest(self) -> str:
        return surface_digest(self.observed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "server": self.server,
            "session_id": self.session_id,
            "observed": list(self.observed),
            "enumerated": list(self.enumerated),
            "digest": self.digest,
            "at": self.at.isoformat(),
        }


@dataclass(frozen=True)
class SurfaceChange:
    """A change in one server's observed surface between two sessions."""

    server: str
    session_id: str
    prev_session_id: str
    prev_digest: str
    digest: str
    added: tuple[str, ...]
    removed: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "server": self.server,
            "session_id": self.session_id,
            "prev_session_id": self.prev_session_id,
            "prev_digest": self.prev_digest,
            "digest": self.digest,
            "added": list(self.added),
            "removed": list(self.removed),
        }


@dataclass
class _Acc:
    server: str
    session_id: str
    observed: set[str] = field(default_factory=set)
    enumerated: set[str] = field(default_factory=set)
    digest: str | None = None
    at: datetime | None = None


def _carrier_arguments(record: AgentRecord) -> dict[str, Any] | None:
    if record.tool.name != MCP_SURFACE_TOOL or not isinstance(record.tool.arguments, dict):
        return None
    return record.tool.arguments


def survey(records: Sequence[AgentRecord]) -> list[SurfaceState]:
    """Every ``(server, session)`` surface seen, ordered by first sighting.

    The observed set comes from usage (``tool.server``/``tool.name``); an
    ``mcp-surface`` carrier may add the enumerated set and a recorded digest.
    """
    accs: dict[tuple[str, str], _Acc] = {}
    order: list[tuple[str, str]] = []

    def bucket(server: str, session_id: str, at: datetime | None) -> _Acc:
        key = (server, session_id)
        acc = accs.get(key)
        if acc is None:
            acc = _Acc(server=server, session_id=session_id)
            accs[key] = acc
            order.append(key)
        if at is not None and (acc.at is None or at < acc.at):
            acc.at = at
        return acc

    for record in records:
        if record.tool.name == MCP_SURFACE_TOOL:
            args = _carrier_arguments(record)
            if args is None:
                continue
            server = str(args.get("server", "unknown"))
            acc = bucket(server, record.session_id, record.started_at)
            observed = args.get("observed")
            if isinstance(observed, list):
                acc.observed.update(str(item) for item in observed)
            enumerated = args.get("enumerated")
            if isinstance(enumerated, list):
                acc.enumerated.update(str(item) for item in enumerated)
            stored = args.get("digest")
            if isinstance(stored, str):
                acc.digest = stored
        elif record.tool.server is not None:
            acc = bucket(record.tool.server, record.session_id, record.started_at)
            acc.observed.add(record.tool.name)

    states: list[SurfaceState] = []
    for key in order:
        acc = accs[key]
        observed = tuple(sorted(acc.observed))
        states.append(
            SurfaceState(
                server=acc.server,
                session_id=acc.session_id,
                observed=observed,
                enumerated=tuple(sorted(acc.enumerated)),
                digest=acc.digest or surface_digest(observed),
                at=acc.at or datetime.min.replace(tzinfo=timezone.utc),
            )
        )
    return states


def detect_surface_changes(
    records: Sequence[AgentRecord], *, server: str | None = None
) -> list[SurfaceChange]:
    """Consecutive-session surface changes per server (first sighting is not one)."""
    by_server: dict[str, list[SurfaceState]] = {}
    for state in survey(records):
        if server is not None and state.server != server:
            continue
        by_server.setdefault(state.server, []).append(state)

    changes: list[SurfaceChange] = []
    for name in sorted(by_server):
        states = sorted(by_server[name], key=lambda state: state.at)
        for prev, current in zip(states, states[1:], strict=False):
            if current.digest == prev.digest:
                continue
            changes.append(
                SurfaceChange(
                    server=name,
                    session_id=current.session_id,
                    prev_session_id=prev.session_id,
                    prev_digest=prev.digest,
                    digest=current.digest,
                    added=tuple(sorted(set(current.observed) - set(prev.observed))),
                    removed=tuple(sorted(set(prev.observed) - set(current.observed))),
                )
            )
    return changes


def carrier_records(session_id: str, states: Sequence[SurfaceState]) -> list[AgentRecord]:
    """Metadata-only ``mcp-surface`` carrier records for one session."""
    records: list[AgentRecord] = []
    for state in states:
        records.append(
            AgentRecord(
                session_id=session_id,
                agent=AgentIdentity(identity="agentwatch"),
                tool=ToolCall(
                    name=MCP_SURFACE_TOOL,
                    server=state.server,
                    arguments={
                        "server": state.server,
                        "observed": list(state.observed),
                        "enumerated": list(state.enumerated),
                        "digest": state.digest,
                    },
                    privacy_mode=RecordPrivacyMode.METADATA_ONLY,
                ),
                outcome=Outcome.OK,
                started_at=state.at,
                producer=MARKER_PRODUCER,
                step_type=StepType.OBSERVE,
            )
        )
    return records


def surface_event(change: SurfaceChange, *, at: datetime) -> SecurityEvent:
    """The ``tool-surface-changed`` observation for one detected change."""
    return SecurityEvent(
        type=SecurityEventType.TOOL_SURFACE_CHANGED,
        emitted_at=at,
        emitter="agentwatch",
        tool=change.server,
        evidence={
            "server": change.server,
            "added": list(change.added),
            "removed": list(change.removed),
            "prev_digest": change.prev_digest,
            "digest": change.digest,
        },
    )


def record_mcp_surface(
    store: RecordStore, session_id: str, *, now: datetime | None = None
) -> list[SurfaceChange]:
    """Append carriers for a session and emit an event per detected change.

    Compares the session's observed surface against the latest prior
    ``(server, session)`` surface. A first-seen server emits no event.
    """
    moment = now or datetime.now(timezone.utc)
    all_records = store.records()
    states = [state for state in survey(all_records) if state.session_id == session_id]
    # Detect changes using records *before* this session's carriers exist.
    changes = [
        change for change in detect_surface_changes(all_records) if change.session_id == session_id
    ]
    for record in carrier_records(session_id, states):
        store.append(record)
    for change in changes:
        store.append(
            AgentRecord(
                session_id=session_id,
                agent=AgentIdentity(identity="agentwatch"),
                tool=ToolCall(name=SURFACE_EVENT_TOOL, server=change.server),
                outcome=Outcome.OK,
                started_at=moment,
                producer=MARKER_PRODUCER,
                step_type=StepType.OBSERVE,
                security_event=surface_event(change, at=moment),
            )
        )
    return changes


def render_snapshots(states: Sequence[SurfaceState]) -> str:
    lines = ["SERVER\tSESSION\tOBSERVED\tENUMERATED\tDIGEST"]
    for state in states:
        lines.append(
            f"{state.server}\t{state.session_id}\t{','.join(state.observed)}\t"
            f"{','.join(state.enumerated)}\t{state.digest}"
        )
    return "\n".join(lines)


def render_changes(changes: Sequence[SurfaceChange]) -> str:
    if not changes:
        return "no tool-surface changes"
    lines = ["SERVER\tSESSION\tADDED\tREMOVED\tPREV_DIGEST\tDIGEST"]
    for change in changes:
        lines.append(
            f"{change.server}\t{change.session_id}\t{','.join(change.added)}\t"
            f"{','.join(change.removed)}\t{change.prev_digest}\t{change.digest}"
        )
    return "\n".join(lines)


__all__ = [
    "MCP_SURFACE_TOOL",
    "SURFACE_EVENT_TOOL",
    "SurfaceChange",
    "SurfaceState",
    "carrier_records",
    "detect_surface_changes",
    "record_mcp_surface",
    "render_changes",
    "render_snapshots",
    "surface_digest",
    "surface_event",
    "survey",
]
