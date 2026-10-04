"""``agentwatch tree`` — the subagent fan-out (M17 S17, PRD 33).

A4 captures subagent attribution (``agent_id``/``agent_type`` -> identity) but
every view is a flat list. This renders the structure: parent -> subagent
fan-out with per-node tool counts, outcomes, duration, and tokens. Parallel
branches are siblings; an orphan child (no matching parent span) is attached to
the root with a note; recursion is bounded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from agentwatch.records import AgentRecord
from agentwatch.replay import replay_session
from agentwatch.store import RecordStore

MAX_DEPTH = 16

# Marker/internal records are not agent behavior.
_INTERNAL_TOOLS = frozenset(
    {
        "recording-gap",
        "hook-error",
        "session-purge",
        "operator-note",
        "store-access",
        "harness-drift",
        "session-usage",
        "external-event",
        "archive-anchor",
        "archive-restored",
    }
)


@dataclass(frozen=True)
class TreeNode:
    """One agent (the session root or a subagent) and its fan-out."""

    key: str
    tools: int
    outcomes: dict[str, int] = field(default_factory=dict)
    duration_ms: float | None = None
    tokens: int = 0
    cost_usd: float | None = None
    first_at: datetime | None = None
    last_at: datetime | None = None
    orphan: bool = False
    truncated: bool = False
    children: tuple[TreeNode, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "tools": self.tools,
            "outcomes": dict(self.outcomes),
            "duration_ms": self.duration_ms,
            "tokens": self.tokens,
            "cost_usd": self.cost_usd,
            "first_at": self.first_at.isoformat() if self.first_at else None,
            "last_at": self.last_at.isoformat() if self.last_at else None,
            "orphan": self.orphan,
            "truncated": self.truncated,
            "children": [child.to_dict() for child in self.children],
        }


def _node_key(record: AgentRecord) -> str:
    return record.agent.identity or record.agent.name or "unknown"


@dataclass
class _Acc:
    key: str
    tools: int = 0
    outcomes: dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0
    has_duration: bool = False
    tokens: int = 0
    cost_usd: float = 0.0
    has_cost: bool = False
    first_at: datetime | None = None
    last_at: datetime | None = None

    def add(self, record: AgentRecord) -> None:
        if record.tool.name not in _INTERNAL_TOOLS:
            self.tools += 1
        outcome = record.outcome.value
        self.outcomes[outcome] = self.outcomes.get(outcome, 0) + 1
        if record.duration_ms is not None:
            self.duration_ms += record.duration_ms
            self.has_duration = True
        if record.tokens:
            self.tokens += record.tokens
        if record.cost_usd is not None:
            self.cost_usd += record.cost_usd
            self.has_cost = True
        if self.first_at is None or record.started_at < self.first_at:
            self.first_at = record.started_at
        if self.last_at is None or record.started_at > self.last_at:
            self.last_at = record.started_at


def _parent_of(
    key: str, records: list[AgentRecord], span_owner: dict[str, str], root: str
) -> tuple[str, bool]:
    for record in records:
        if record.parent_span_id and record.parent_span_id in span_owner:
            parent = span_owner[record.parent_span_id]
            if parent != key:
                return parent, False
    return root, True


def build_tree(store: RecordStore, session_id: str) -> TreeNode:
    """Build the agent fan-out for one session (never errors on no subagents)."""
    records = [
        record
        for record in replay_session(store, session_id)
        if record.tool.name not in _INTERNAL_TOOLS
    ]
    if not records:
        return TreeNode(key=session_id, tools=0)

    root_key = _node_key(records[0])
    span_owner: dict[str, str] = {}
    for record in records:
        if record.span_id is not None:
            span_owner.setdefault(record.span_id, _node_key(record))

    by_key: dict[str, list[AgentRecord]] = {}
    for record in records:
        by_key.setdefault(_node_key(record), []).append(record)

    children: dict[str, list[str]] = {}
    orphan_of: dict[str, bool] = {}
    for key in by_key:
        if key == root_key:
            continue
        parent, orphan = _parent_of(key, by_key[key], span_owner, root_key)
        children.setdefault(parent, []).append(key)
        orphan_of[key] = orphan

    def build(key: str, depth: int) -> TreeNode:
        accumulator = _Acc(key)
        for record in by_key.get(key, []):
            accumulator.add(record)
        child_nodes: list[TreeNode] = []
        if depth < MAX_DEPTH:
            for child in sorted(children.get(key, [])):
                child_nodes.append(build(child, depth + 1))
        return TreeNode(
            key=key,
            tools=accumulator.tools,
            outcomes=dict(sorted(accumulator.outcomes.items())),
            duration_ms=accumulator.duration_ms if accumulator.has_duration else None,
            tokens=accumulator.tokens,
            cost_usd=accumulator.cost_usd if accumulator.has_cost else None,
            first_at=accumulator.first_at,
            last_at=accumulator.last_at,
            orphan=orphan_of.get(key, False),
            truncated=depth >= MAX_DEPTH,
            children=tuple(child_nodes),
        )

    root = build(root_key, 0)
    # Keys that named themselves as their own parent cannot happen, but keys not
    # reachable from the root (an orphan cycle) are attached to the root.
    reachable = _reachable(root)
    extra = [key for key in by_key if key not in reachable and key != root_key]
    if extra:
        attached = tuple(build(key, 1) for key in sorted(extra))
        root = TreeNode(
            key=root.key,
            tools=root.tools,
            outcomes=root.outcomes,
            duration_ms=root.duration_ms,
            tokens=root.tokens,
            cost_usd=root.cost_usd,
            first_at=root.first_at,
            last_at=root.last_at,
            orphan=root.orphan,
            truncated=root.truncated,
            children=(*root.children, *attached),
        )
    return root


def _reachable(node: TreeNode) -> set[str]:
    seen = {node.key}
    for child in node.children:
        seen |= _reachable(child)
    return seen


def sort_by_cost(root: TreeNode) -> TreeNode:
    """Return a copy of the tree with siblings ordered by cost (desc), then tokens."""
    children = tuple(sort_by_cost(child) for child in root.children)
    ordered = tuple(sorted(children, key=lambda n: (n.cost_usd or 0.0, n.tokens), reverse=True))
    return TreeNode(
        key=root.key,
        tools=root.tools,
        outcomes=root.outcomes,
        duration_ms=root.duration_ms,
        tokens=root.tokens,
        cost_usd=root.cost_usd,
        first_at=root.first_at,
        last_at=root.last_at,
        orphan=root.orphan,
        truncated=root.truncated,
        children=ordered,
    )


def render_tree(root: TreeNode) -> str:
    """Render the fan-out as an indented tree."""
    lines = [f"agentwatch tree {root.key}"]

    def walk(node: TreeNode, depth: int) -> None:
        flags = []
        if node.orphan:
            flags.append("orphan -> attached to root")
        if node.truncated:
            flags.append("depth truncated")
        suffix = f"  [{'; '.join(flags)}]" if flags else ""
        outcome = " ".join(f"{key}={value}" for key, value in sorted(node.outcomes.items()))
        cost = "unknown" if node.cost_usd is None else f"${node.cost_usd:.4f}"
        lines.append(
            f"{'  ' * (depth + 1)}- {node.key}: tools={node.tools} {outcome} "
            f"duration={node.duration_ms or 0:.0f}ms tokens={node.tokens} cost={cost}{suffix}"
        )
        for child in node.children:
            walk(child, depth + 1)

    walk(root, 0)
    return "\n".join(lines)


__all__ = ["MAX_DEPTH", "TreeNode", "build_tree", "render_tree", "sort_by_cost"]
