"""``agentwatch trace`` — cross-host causal reconstruction (M26 TRACE-2, PRD 41).

Single-host ``tree`` (M17 S17) is not enough for multi-agent attribution: the
causal chain for an outcome can span agents, processes, and hosts (G2). This
reconstructs one trace across everything a fleet aggregate store holds, joined
by W3C ``traceparent``/``trace_id`` and linked by ``parent_span_id``.

Two honesty rules:

* **structure over timestamps** — parentage defines the tree; a child whose
  timestamps disagree with its parent because of cross-host clock skew is
  surfaced (``skew_ms`` + a ``clock-skew`` gap), never silently reordered.
* **breaks are classified** — a record whose parent span is absent is attached
  to the root as an orphan with a ``missing-parent`` gap; it is never dropped.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agentwatch.records import AgentRecord
from agentwatch.trace_context import parse_traceparent

MAX_DEPTH = 32
SKEW_TOLERANCE_MS = 1000.0


def record_trace_id(record: AgentRecord) -> str | None:
    """A record's trace id: the parsed ``traceparent`` first, else ``trace_id``.

    A malformed ``traceparent`` fails closed to the record's own ``trace_id`` —
    a correlation is never invented (TRACE-1 discipline).
    """
    if record.traceparent:
        context = parse_traceparent(record.traceparent)
        if context is not None:
            return context.trace_id
    return record.trace_id


def records_for_trace(records: Iterable[AgentRecord], trace_id: str) -> list[AgentRecord]:
    """Every record correlated to ``trace_id``, across sessions and hosts."""
    return [record for record in records if record_trace_id(record) == trace_id]


@dataclass(frozen=True)
class TraceNode:
    """One span in a cross-host causal tree."""

    span_id: str
    parent_span_id: str | None
    trace_id: str
    host: str | None
    session_id: str
    agent: str
    tool: str
    outcome: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = None
    skew_ms: float | None = None
    orphan: bool = False
    truncated: bool = False
    children: tuple[TraceNode, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "trace_id": self.trace_id,
            "host": self.host,
            "session_id": self.session_id,
            "agent": self.agent,
            "tool": self.tool,
            "outcome": self.outcome,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_ms": self.duration_ms,
            "skew_ms": self.skew_ms,
            "orphan": self.orphan,
            "truncated": self.truncated,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(frozen=True)
class TraceTree:
    """A reconstructed trace: its roots, the hosts it spans, and its gaps."""

    trace_id: str
    records: int
    hosts: tuple[str, ...]
    gaps: tuple[dict[str, Any], ...] = ()
    roots: tuple[TraceNode, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "records": self.records,
            "hosts": list(self.hosts),
            "gaps": [dict(gap) for gap in self.gaps],
            "roots": [root.to_dict() for root in self.roots],
        }


def _span_key(record: AgentRecord) -> str:
    return record.span_id if record.span_id is not None else f"{record.session_id}:no-span"


def build_trace(records: Iterable[AgentRecord], trace_id: str) -> TraceTree:
    """Reconstruct the causal tree for ``trace_id`` (never errors on a gap)."""
    selected = records_for_trace(records, trace_id)
    gaps: list[dict[str, Any]] = []

    by_span: dict[str, AgentRecord] = {}
    for record in selected:
        key = _span_key(record)
        if record.span_id is None:
            gaps.append({"reason": "no-span-id", "session_id": record.session_id})
        by_span.setdefault(key, record)

    children: dict[str, list[str]] = {}
    roots: list[str] = []
    orphan_of: dict[str, bool] = {}
    for key, record in by_span.items():
        parent = record.parent_span_id
        if parent is None:
            roots.append(key)
        elif parent in by_span and parent != key:
            children.setdefault(parent, []).append(key)
        else:
            roots.append(key)
            orphan_of[key] = True
            gaps.append(
                {"reason": "missing-parent", "span_id": key, "parent_span_id": parent}
            )

    def build(key: str, depth: int, visited: frozenset[str]) -> TraceNode:
        record = by_span[key]
        parent = record.parent_span_id
        skew_ms: float | None = None
        if parent is not None and parent in by_span and parent != key:
            delta = (record.started_at - by_span[parent].started_at).total_seconds() * 1000
            skew_ms = delta
            if delta < -SKEW_TOLERANCE_MS:
                gaps.append(
                    {
                        "reason": "clock-skew",
                        "span_id": key,
                        "host": record.host,
                        "skew_ms": delta,
                    }
                )
        nodes: list[TraceNode] = []
        if depth < MAX_DEPTH:
            for child in sorted(children.get(key, []), key=lambda c: by_span[c].started_at):
                if child in visited:
                    gaps.append({"reason": "cycle", "span_id": child})
                    continue
                nodes.append(build(child, depth + 1, visited | {child}))
        return TraceNode(
            span_id=key,
            parent_span_id=parent,
            trace_id=trace_id,
            host=record.host,
            session_id=record.session_id,
            agent=record.agent.identity or record.agent.name or "unknown",
            tool=record.tool.name,
            outcome=record.outcome.value,
            started_at=record.started_at,
            ended_at=record.ended_at,
            duration_ms=record.duration_ms,
            skew_ms=skew_ms,
            orphan=orphan_of.get(key, False),
            truncated=depth >= MAX_DEPTH,
            children=tuple(nodes),
        )

    root_keys = roots or list(by_span)
    root_nodes: list[TraceNode] = []
    for key in sorted(root_keys, key=lambda k: by_span[k].started_at):
        if key in by_span:
            root_nodes.append(build(key, 0, frozenset({key})))

    # Any span not reachable from a declared root (e.g. a cycle) is attached so
    # nothing is lost. Reachability is structural, independent of timestamps.
    reachable: set[str] = set()

    def mark(nodes: tuple[TraceNode, ...]) -> None:
        for node in nodes:
            reachable.add(node.span_id)
            mark(node.children)

    mark(tuple(root_nodes))
    for key in by_span:
        if key not in reachable:
            root_nodes.append(build(key, 0, frozenset({key})))
            gaps.append({"reason": "unreachable", "span_id": key})

    hosts = tuple(sorted({record.host for record in selected if record.host is not None}))
    return TraceTree(
        trace_id=trace_id,
        records=len(selected),
        hosts=hosts,
        gaps=tuple(gaps),
        roots=tuple(root_nodes),
    )


def replay_trace(records: Iterable[AgentRecord], session_id: str) -> list[AgentRecord]:
    """A session's records plus every record sharing its trace ids, oldest-first.

    This is what ``replay <session> --trace`` uses to pull a cross-host causal
    chain into one timeline.
    """
    source = list(records)
    trace_ids = {
        trace
        for record in source
        if record.session_id == session_id
        for trace in [record_trace_id(record)]
        if trace is not None
    }
    selected = [
        record for record in source if record_trace_id(record) in trace_ids
    ] if trace_ids else [record for record in source if record.session_id == session_id]
    return sorted(selected, key=lambda record: record.started_at)


def render_trace(tree: TraceTree) -> str:
    """Render the reconstructed trace as an indented causal tree."""
    lines = [
        f"agentwatch trace {tree.trace_id} "
        f"(records={tree.records} hosts={len(tree.hosts)})"
    ]

    def walk(node: TraceNode, depth: int) -> None:
        flags = []
        if node.orphan:
            flags.append("orphan: missing parent")
        if node.truncated:
            flags.append("depth truncated")
        if node.skew_ms is not None and node.skew_ms < -SKEW_TOLERANCE_MS:
            flags.append(f"clock-skew {node.skew_ms:.0f}ms")
        suffix = f"  [{'; '.join(flags)}]" if flags else ""
        host = node.host or "-"
        lines.append(
            f"{'  ' * (depth + 1)}- {node.span_id} host={host} agent={node.agent} "
            f"{node.tool} {node.outcome} {node.started_at.isoformat()}{suffix}"
        )
        for child in node.children:
            walk(child, depth + 1)

    for root in tree.roots:
        walk(root, 0)
    for gap in tree.gaps:
        lines.append(f"  ! {gap['reason']}: {gap}")
    return "\n".join(lines)


def trace_to_json(tree: TraceTree) -> dict[str, Any]:
    """Serialize a reconstructed trace for ``--json`` output."""
    return tree.to_dict()


__all__ = [
    "MAX_DEPTH",
    "SKEW_TOLERANCE_MS",
    "TraceNode",
    "TraceTree",
    "build_trace",
    "record_trace_id",
    "records_for_trace",
    "render_trace",
    "replay_trace",
    "trace_to_json",
]
