"""``agentwatch impact`` — a session's change footprint (M17 S3, PRD 33).

Answers "what did it touch?" with a grouped, deduplicated footprint: files
written/edited/deleted, side-effecting commands, network destinations, VCS
actions, and credential-adjacent touches, plus a blast-radius summary and the
"widest action" line. Descriptive only — no score, no verdict.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from agentwatch.classify import (
    CLASSIFIER_VERSION,
    CMD_DESTRUCTIVE,
    CMD_INSTALL,
    CMD_MIGRATION,
    CMD_SERVICE,
    CREDENTIAL,
    EXACT,
    FILE_DELETE,
    FILE_EDIT,
    FILE_WRITE,
    HEURISTIC,
    NETWORK,
    UNCLASSIFIED,
    VCS,
    WIDEST_ORDER,
    Fact,
    classify_record,
)
from agentwatch.denials import DenialSequence, denial_sequences
from agentwatch.identity import Attribution, attribution_for
from agentwatch.permission_mode import ModeInterval, bypass_intervals
from agentwatch.query import since_cutoff
from agentwatch.records import AgentRecord
from agentwatch.replay import replay_session
from agentwatch.store import RecordStore

_FILE_CATEGORIES = (FILE_WRITE, FILE_EDIT, FILE_DELETE)
_COMMAND_CATEGORIES = (CMD_INSTALL, CMD_MIGRATION, CMD_SERVICE, CMD_DESTRUCTIVE)
_CATEGORY_LABEL = {
    FILE_WRITE: "files written",
    FILE_EDIT: "files edited",
    FILE_DELETE: "files deleted",
    CMD_INSTALL: "package installs",
    CMD_MIGRATION: "migrations",
    CMD_SERVICE: "service changes",
    CMD_DESTRUCTIVE: "destructive commands",
    NETWORK: "network destinations",
    VCS: "VCS actions",
    CREDENTIAL: "credential-adjacent touches",
    UNCLASSIFIED: "unclassified",
}


@dataclass(frozen=True)
class ImpactEntry:
    """One deduplicated non-file fact."""

    category: str
    target: str | None
    confidence: str
    detail: str


@dataclass(frozen=True)
class FileFootprint:
    """One deduplicated touched path."""

    path: str
    actions: tuple[str, ...]
    confidence: str
    count: int
    first_at: datetime
    last_at: datetime
    outside_project: bool


@dataclass(frozen=True)
class ImpactReport:
    """A session's whole change footprint."""

    session_id: str
    classifier_version: str
    since: str | None = None
    arguments_captured: bool = True
    files: tuple[FileFootprint, ...] = ()
    commands: tuple[ImpactEntry, ...] = ()
    network: tuple[ImpactEntry, ...] = ()
    vcs: tuple[ImpactEntry, ...] = ()
    credentials: tuple[ImpactEntry, ...] = ()
    unclassified: tuple[ImpactEntry, ...] = ()
    counts: dict[str, int] = field(default_factory=dict)
    widest_action: str = "-"
    records: int = 0
    denials: tuple[DenialSequence, ...] = ()
    attribution: Attribution | None = None
    bypass_intervals: tuple[ModeInterval, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "classifier_version": self.classifier_version,
            "since": self.since,
            "arguments_captured": self.arguments_captured,
            "records": self.records,
            "attribution": self.attribution.to_dict() if self.attribution else None,
            "counts": dict(self.counts),
            "widest_action": self.widest_action,
            "files": [
                {
                    "path": f.path,
                    "actions": list(f.actions),
                    "confidence": f.confidence,
                    "count": f.count,
                    "first_at": f.first_at.isoformat(),
                    "last_at": f.last_at.isoformat(),
                    "outside_project": f.outside_project,
                }
                for f in self.files
            ],
            "commands": [self._entry(e) for e in self.commands],
            "network": [self._entry(e) for e in self.network],
            "vcs": [self._entry(e) for e in self.vcs],
            "credentials": [self._entry(e) for e in self.credentials],
            "unclassified": [self._entry(e) for e in self.unclassified],
            "bypass_intervals": [interval.to_dict() for interval in self.bypass_intervals],
            "denials": [
                {
                    "session_id": sequence.session_id,
                    "denied_tool": sequence.denied_tool,
                    "denied_at": sequence.denied_at.isoformat(),
                    "reason": sequence.reason,
                    "follow_ups": [
                        {"tool": f.tool, "outcome": f.outcome, "at": f.at.isoformat()}
                        for f in sequence.follow_ups
                    ],
                }
                for sequence in self.denials
            ],
        }

    @staticmethod
    def _entry(entry: ImpactEntry) -> dict[str, Any]:
        return {
            "category": entry.category,
            "target": entry.target,
            "confidence": entry.confidence,
            "detail": entry.detail,
        }


def _dedupe(facts: Iterable[tuple[ImpactEntry, AgentRecord]]) -> tuple[ImpactEntry, ...]:
    seen: set[tuple[str, str | None, str]] = set()
    result: list[ImpactEntry] = []
    for entry, _record in facts:
        key = (entry.category, entry.target, entry.detail)
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return tuple(result)


class _FileAcc:
    def __init__(self, path: str) -> None:
        self.path = path
        self.actions: set[str] = set()
        self.count = 0
        self.confidence = HEURISTIC
        self.first_at: datetime | None = None
        self.last_at: datetime | None = None
        self.outside_project = False


def build_impact(
    store: RecordStore,
    session_id: str,
    *,
    since: str | None = None,
    now: datetime | None = None,
) -> ImpactReport:
    """Build the change footprint for one session (records older than ``since`` dropped)."""
    cutoff = since_cutoff(since, now=now) if since is not None else None
    records = [
        record
        for record in replay_session(store, session_id)
        if cutoff is None or record.started_at >= cutoff
    ]

    files: dict[str, _FileAcc] = {}
    commands: list[tuple[ImpactEntry, AgentRecord]] = []
    network: list[tuple[ImpactEntry, AgentRecord]] = []
    vcs: list[tuple[ImpactEntry, AgentRecord]] = []
    credentials: list[tuple[ImpactEntry, AgentRecord]] = []
    unclassified: list[tuple[ImpactEntry, AgentRecord]] = []
    arguments_captured = False

    for record in records:
        if record.tool.arguments is not None:
            arguments_captured = True
        for fact in classify_record(record):
            _accumulate(
                fact,
                record,
                files=files,
                commands=commands,
                network=network,
                vcs=vcs,
                credentials=credentials,
                unclassified=unclassified,
            )

    file_footprints = tuple(
        FileFootprint(
            path=acc.path,
            actions=tuple(sorted(acc.actions)),
            confidence=acc.confidence,
            count=acc.count,
            first_at=acc.first_at or datetime.min,
            last_at=acc.last_at or datetime.min,
            outside_project=acc.outside_project,
        )
        for acc in sorted(files.values(), key=lambda a: a.path)
    )

    grouped = {
        FILE_WRITE: sum(1 for f in file_footprints if FILE_WRITE in f.actions),
        FILE_EDIT: sum(1 for f in file_footprints if FILE_EDIT in f.actions),
        FILE_DELETE: sum(1 for f in file_footprints if FILE_DELETE in f.actions),
        CMD_INSTALL: _count(commands, CMD_INSTALL),
        CMD_MIGRATION: _count(commands, CMD_MIGRATION),
        CMD_SERVICE: _count(commands, CMD_SERVICE),
        CMD_DESTRUCTIVE: _count(commands, CMD_DESTRUCTIVE),
        NETWORK: len(network),
        VCS: len(vcs),
        CREDENTIAL: len(credentials),
        UNCLASSIFIED: len(unclassified),
    }
    return ImpactReport(
        session_id=session_id,
        classifier_version=CLASSIFIER_VERSION,
        since=since,
        arguments_captured=arguments_captured,
        files=file_footprints,
        commands=_dedupe(commands),
        network=_dedupe(network),
        vcs=_dedupe(vcs),
        credentials=_dedupe(credentials),
        unclassified=_dedupe(unclassified),
        counts=grouped,
        widest_action=_widest(
            grouped,
            file_footprints,
            {
                CMD_DESTRUCTIVE: commands,
                CMD_SERVICE: commands,
                CMD_MIGRATION: commands,
                CMD_INSTALL: commands,
                NETWORK: network,
                VCS: vcs,
                CREDENTIAL: credentials,
            },
        ),
        records=len(records),
        denials=denial_sequences(records),
        attribution=attribution_for(records[-1]) if records else None,
        bypass_intervals=bypass_intervals(records),
    )


def _accumulate(
    fact: Fact,
    record: AgentRecord,
    *,
    files: dict[str, _FileAcc],
    commands: list[tuple[ImpactEntry, AgentRecord]],
    network: list[tuple[ImpactEntry, AgentRecord]],
    vcs: list[tuple[ImpactEntry, AgentRecord]],
    credentials: list[tuple[ImpactEntry, AgentRecord]],
    unclassified: list[tuple[ImpactEntry, AgentRecord]],
) -> None:
    entry = ImpactEntry(fact.category, fact.target, fact.confidence, fact.detail)
    if fact.category in _FILE_CATEGORIES:
        if fact.target is None:
            unclassified.append((entry, record))
            return
        acc = files.setdefault(fact.target, _FileAcc(fact.target))
        acc.actions.add(fact.category)
        acc.count += 1
        if fact.confidence == EXACT:
            acc.confidence = EXACT
        if acc.first_at is None or record.started_at < acc.first_at:
            acc.first_at = record.started_at
        if acc.last_at is None or record.started_at > acc.last_at:
            acc.last_at = record.started_at
        if _outside_project(fact.target, record.project):
            acc.outside_project = True
    elif fact.category in _COMMAND_CATEGORIES:
        commands.append((entry, record))
    elif fact.category == NETWORK:
        network.append((entry, record))
    elif fact.category == VCS:
        vcs.append((entry, record))
    elif fact.category == CREDENTIAL:
        credentials.append((entry, record))
    else:
        unclassified.append((entry, record))


def _count(entries: list[tuple[ImpactEntry, AgentRecord]], category: str) -> int:
    return sum(1 for entry, _ in entries if entry.category == category)


def _outside_project(target: str, project: str | None) -> bool:
    if not project or not target.startswith("/"):
        return False
    try:
        Path(target).relative_to(project)
    except ValueError:
        return True
    return False


def _widest(
    counts: dict[str, int],
    files: tuple[FileFootprint, ...],
    pools: dict[str, list[tuple[ImpactEntry, AgentRecord]]],
) -> str:
    for category in WIDEST_ORDER:
        if counts.get(category, 0) <= 0:
            continue
        if category in _FILE_CATEGORIES:
            sample = next((f.path for f in files if category in f.actions), "?")
            return f"{category}: {sample} ({counts[category]})"
        pool = pools.get(category, [])
        sample = next((e.target or e.detail for e, _ in pool if e.category == category), "?")
        return f"{category}: {sample} ({counts[category]})"
    return "-"


def render_impact(report: ImpactReport) -> str:
    """Render a footprint as short human-readable text."""
    lines = [f"agentwatch impact {report.session_id} (classifier {report.classifier_version})"]
    if report.attribution is not None:
        lines.append(f"  attribution: {report.attribution.label()}")
    if not report.arguments_captured:
        lines.append(
            "  note: tool arguments were not captured (metadata-only); "
            "enable capture for a full footprint"
        )
    lines.append(f"  widest action: {report.widest_action}")
    for interval in report.bypass_intervals:
        lines.append(
            f"  bypass interval: {interval.start.isoformat()} -> {interval.end.isoformat()} "
            f"({interval.calls} call(s))"
        )
    if report.files:
        lines.append("  files:")
        for footprint in report.files:
            flags = " [outside project]" if footprint.outside_project else ""
            lines.append(
                f"    {'/'.join(a.split(':')[1] for a in footprint.actions)}"
                f" {footprint.path} ({footprint.confidence}, x{footprint.count}){flags}"
            )
    for label, entries in (
        ("side effects", report.commands),
        ("network", report.network),
        ("vcs", report.vcs),
        ("credential-adjacent", report.credentials),
        ("unclassified", report.unclassified),
    ):
        if not entries:
            continue
        lines.append(f"  {label}:")
        for entry in entries:
            target = f" {entry.target}" if entry.target else ""
            lines.append(f"    {entry.category}{target} ({entry.confidence})")
    if not report.files and not any(
        (report.commands, report.network, report.vcs, report.credentials, report.unclassified)
    ):
        lines.append("  no classifiable activity in the captured records")
    if report.denials:
        from agentwatch.denials import render_sequences

        lines.append(render_sequences(report.denials))
    return "\n".join(lines)


def category_label(category: str) -> str:
    """A human label for a category (used by the digest, S37)."""
    return _CATEGORY_LABEL.get(category, category)


__all__ = [
    "FileFootprint",
    "ImpactEntry",
    "ImpactReport",
    "build_impact",
    "category_label",
    "render_impact",
]
