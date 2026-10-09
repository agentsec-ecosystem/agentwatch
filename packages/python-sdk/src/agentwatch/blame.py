"""``agentwatch blame`` — the file-centric reverse index (M17 S18, PRD 33).

Given a path, list every record whose arguments touched it, newest first — git
blame for agent activity, including edits later overwritten. Reuses the S3
classifier: a path in a structured ``Write``/``Edit`` argument is ``exact``; a
path inside a shell command is ``heuristic``. Paths on both sides are normalized
against the project root; symlinks, ``~`` and ``../`` are documented limits.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

from agentwatch.classify import Fact, classify_record
from agentwatch.identity import Attribution, attribution_for
from agentwatch.query import since_cutoff
from agentwatch.records import AgentRecord
from agentwatch.store import RecordStore

FILE_CATEGORIES = frozenset({"file:write", "file:edit", "file:delete", "file:read"})


@dataclass(frozen=True)
class BlameHit:
    """One record that touched the queried path."""

    session_id: str
    agent: str
    tool: str
    outcome: str
    confidence: str
    action: str
    at: datetime
    seq: int
    attribution: Attribution = Attribution(agent="unknown")


@dataclass(frozen=True)
class BlameReport:
    """Every record touching one path, newest first."""

    query: str
    normalized: str
    project: str | None = None
    since: str | None = None
    hits: tuple[BlameHit, ...] = ()

    @property
    def sessions(self) -> tuple[str, ...]:
        order: list[str] = []
        for hit in self.hits:
            if hit.session_id not in order:
                order.append(hit.session_id)
        return tuple(order)

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "normalized": self.normalized,
            "project": self.project,
            "since": self.since,
            "sessions": list(self.sessions),
            "hits": [
                {
                    "session_id": hit.session_id,
                    "agent": hit.agent,
                    "tool": hit.tool,
                    "outcome": hit.outcome,
                    "confidence": hit.confidence,
                    "action": hit.action,
                    "at": hit.at.isoformat(),
                    "attribution": hit.attribution.to_dict(),
                }
                for hit in self.hits
            ],
        }


def normalize_path(path: str, *, project: str | None) -> str:
    """Normalize a possibly-relative path against the project root.

    ``~`` is expanded; ``..``/``.`` are collapsed. Symlinks are **not** resolved
    (documented limit): a worktree or symlinked path may not match its target.
    """
    expanded = os.path.expanduser(path)
    if not os.path.isabs(expanded) and project:
        expanded = os.path.join(project, expanded)
    return os.path.normpath(expanded)


def _target_normalized(fact: Fact, base: str | None) -> str | None:
    if fact.target is None:
        return None
    return normalize_path(fact.target, project=base)


def build_blame(
    store: RecordStore,
    path: str,
    *,
    since: str | None = None,
    project: str | None = None,
    now: datetime | None = None,
) -> BlameReport:
    """List every record touching ``path`` across sessions, newest first."""
    normalized = normalize_path(path, project=project)
    cutoff = since_cutoff(since, now=now) if since is not None else None
    hits: list[BlameHit] = []
    for entry in store.entries():
        record = entry.record
        if record is None:
            continue
        if cutoff is not None and record.started_at < cutoff:
            continue
        if project is not None and record.project != project:
            continue
        for fact in classify_record(record):
            if fact.category not in FILE_CATEGORIES:
                continue
            base = record.project or project
            candidate = _target_normalized(fact, base)
            if candidate is None or candidate != normalized:
                continue
            hits.append(
                BlameHit(
                    session_id=record.session_id,
                    agent=_agent_label(record),
                    tool=record.tool.name,
                    outcome=record.outcome.value,
                    confidence=fact.confidence,
                    action=fact.category,
                    at=record.started_at,
                    seq=entry.seq,
                    attribution=attribution_for(record),
                )
            )
    hits.sort(key=lambda hit: (hit.at, hit.seq), reverse=True)
    return BlameReport(
        query=path,
        normalized=normalized,
        project=project,
        since=since,
        hits=tuple(hits),
    )


def _agent_label(record: AgentRecord) -> str:
    return record.agent.identity or record.agent.name or "unknown"


def render_blame(report: BlameReport) -> str:
    """Render blame hits as short text (newest first)."""
    lines = [f"agentwatch blame {report.normalized}"]
    if not report.hits:
        lines.append("  no records touched this path")
        return "\n".join(lines)
    for hit in report.hits:
        lines.append(
            f"  {hit.at.isoformat()} {hit.session_id} {hit.tool} "
            f"{hit.outcome} {hit.action.split(':')[1]} ({hit.confidence})"
        )
        lines.append(f"    attribution: {hit.attribution.label()}")
    return "\n".join(lines)


def blame_sessions(report: BlameReport) -> str:
    """The distinct sessions that touched the path, newest first."""
    lines = [report.normalized]
    lines.extend(report.sessions)
    return "\n".join(lines)


__all__ = [
    "BlameHit",
    "BlameReport",
    "blame_sessions",
    "build_blame",
    "normalize_path",
    "render_blame",
]
