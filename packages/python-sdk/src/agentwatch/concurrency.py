"""Concurrency report + `ambiguous` attribution (M30 CNC-1, PRD 57).

Parallel / worktree / background agents edit the same paths; ``blame`` and ``at``
show no overlap, so attribution can silently pick the wrong session. This module
reports, deterministically and from evidence only:

* sessions whose activity **overlaps in time** on the same repo/path, and
* **shared-file edits** (a path touched by more than one session),

so ``provenance`` can mark a multi-session range ``ambiguous`` instead of
guessing. No verdicts, no server: a deterministic report over the local store.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from agentwatch.query import since_cutoff
from agentwatch.records import AgentRecord
from agentwatch.store import RecordStore

_FILE_CATEGORIES = frozenset({"file:write", "file:edit", "file:delete"})


def _normalize(path: str, base: str | None) -> str:
    expanded = os.path.expanduser(path)
    if not os.path.isabs(expanded) and base:
        expanded = os.path.join(base, expanded)
    return os.path.normpath(expanded)


@dataclass(frozen=True)
class SessionSpan:
    """A session's activity interval and the paths it touched."""

    session_id: str
    project: str | None
    start: datetime
    end: datetime
    paths: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "project": self.project,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "paths": list(self.paths),
        }


@dataclass(frozen=True)
class Overlap:
    """Two sessions that overlapped in time on at least one shared path."""

    sessions: tuple[str, str]
    start: datetime
    end: datetime
    paths: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "sessions": list(self.sessions),
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "paths": list(self.paths),
        }


@dataclass(frozen=True)
class SharedFile:
    """A path edited by more than one session."""

    path: str
    sessions: tuple[str, ...]
    edits: int

    def to_dict(self) -> dict[str, object]:
        return {"path": self.path, "sessions": list(self.sessions), "edits": self.edits}


@dataclass(frozen=True)
class ConcurrencyReport:
    """A deterministic concurrency rollup for one project/window."""

    project: str | None = None
    since: str | None = None
    spans: tuple[SessionSpan, ...] = ()
    overlaps: tuple[Overlap, ...] = ()
    shared_files: tuple[SharedFile, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "project": self.project,
            "since": self.since,
            "spans": [span.to_dict() for span in self.spans],
            "overlaps": [overlap.to_dict() for overlap in self.overlaps],
            "shared_files": [entry.to_dict() for entry in self.shared_files],
            "notes": list(self.notes),
        }


def _paths_for(record: AgentRecord, base: str | None) -> tuple[str, ...]:
    from agentwatch.classify import classify_record

    paths: list[str] = []
    for fact in classify_record(record):
        if fact.category in _FILE_CATEGORIES and fact.target is not None:
            candidate = _normalize(fact.target, record.project or base)
            if candidate not in paths:
                paths.append(candidate)
    return tuple(paths)


def _spans(records: Iterable[AgentRecord], base: str | None) -> dict[str, SessionSpan]:
    grouped: dict[str, list[AgentRecord]] = {}
    for record in records:
        grouped.setdefault(record.session_id, []).append(record)
    spans: dict[str, SessionSpan] = {}
    for session_id, items in grouped.items():
        start = min(item.started_at for item in items)
        end = max(item.ended_at or item.started_at for item in items)
        paths: list[str] = []
        for item in items:
            for path in _paths_for(item, base):
                if path not in paths:
                    paths.append(path)
        spans[session_id] = SessionSpan(
            session_id=session_id,
            project=items[0].project,
            start=start,
            end=end,
            paths=tuple(sorted(paths)),
        )
    return spans


def _overlaps(spans: dict[str, SessionSpan]) -> tuple[Overlap, ...]:
    ordered = sorted(spans.values(), key=lambda span: (span.start, span.session_id))
    overlaps: list[Overlap] = []
    for index, first in enumerate(ordered):
        for second in ordered[index + 1 :]:
            if first.start > second.end or second.start > first.end:
                continue
            shared = tuple(sorted(set(first.paths) & set(second.paths)))
            if not shared:
                continue
            overlaps.append(
                Overlap(
                    sessions=(first.session_id, second.session_id),
                    start=max(first.start, second.start),
                    end=min(first.end, second.end),
                    paths=shared,
                )
            )
    return tuple(overlaps)


def _shared_files(spans: dict[str, SessionSpan]) -> tuple[SharedFile, ...]:
    sessions_by_path: dict[str, list[str]] = {}
    edits_by_path: dict[str, int] = {}
    for span in spans.values():
        for path in span.paths:
            sessions_by_path.setdefault(path, []).append(span.session_id)
            edits_by_path[path] = edits_by_path.get(path, 0) + 1
    shared = [
        SharedFile(path, tuple(sorted(sessions)), edits_by_path[path])
        for path, sessions in sessions_by_path.items()
        if len(sessions) > 1
    ]
    return tuple(sorted(shared, key=lambda entry: entry.path))


def build_concurrency(
    store: RecordStore,
    *,
    project: str | None = None,
    since: str | None = None,
    now: datetime | None = None,
) -> ConcurrencyReport:
    """Report overlapping sessions and shared-file edits (deterministic)."""
    cutoff = since_cutoff(since, now=now) if since is not None else None
    records = [
        record
        for record in store.records()
        if (project is None or record.project == project)
        and (cutoff is None or record.started_at >= cutoff)
    ]
    spans = _spans(records, project)
    notes: list[str] = []
    if not spans:
        notes.append("no recorded sessions in the window")
    return ConcurrencyReport(
        project=project,
        since=since,
        spans=tuple(sorted(spans.values(), key=lambda span: (span.start, span.session_id))),
        overlaps=_overlaps(spans),
        shared_files=_shared_files(spans),
        notes=tuple(notes),
    )


def render_concurrency(report: ConcurrencyReport) -> str:
    """Render a concurrency report as short text."""
    lines = [f"agentwatch concurrency (project={report.project or '(any)'})"]
    if report.overlaps:
        for overlap in report.overlaps:
            first, second = overlap.sessions
            lines.append(
                f"  overlap {first} <-> {second} "
                f"{overlap.start.isoformat()}..{overlap.end.isoformat()} "
                f"{', '.join(overlap.paths)}"
            )
    else:
        lines.append("  no overlapping sessions")
    for entry in report.shared_files:
        lines.append(f"  shared {entry.path} sessions={','.join(entry.sessions)}")
    for note in report.notes:
        lines.append(f"  note: {note}")
    return "\n".join(lines)


__all__ = [
    "ConcurrencyReport",
    "Overlap",
    "SessionSpan",
    "SharedFile",
    "build_concurrency",
    "render_concurrency",
]
