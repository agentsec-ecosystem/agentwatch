"""``agentwatch oversight`` — authorization and oversight facts (M29 APV-3, PRD 49).

Answers, deterministically and offline: what authorized the calls (authorization
mix), what mode each session ran under, how humans responded to permission
prompts (approve/reject + time-to-decision), and a cls1 destructive/network/
credential-adjacent × authorization cross-tab — the incident question.

Facts only. There is no score or verdict; every ratio carries a denominator, and
latency is shown only when both the prompt and decision timestamps exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median
from typing import Any

from agentwatch.authorization import AUTHORIZATION_TAXONOMY_VERSION
from agentwatch.capabilities import COVERAGE_NONE, COVERAGE_PARTIAL
from agentwatch.classify import (
    CMD_DESTRUCTIVE,
    CREDENTIAL,
    NETWORK,
    UNCLASSIFIED,
    classify_record,
)
from agentwatch.coverage import is_tool_call_record
from agentwatch.permission_mode import effective_modes, is_permission_mode_change, mode_intervals
from agentwatch.query import since_cutoff
from agentwatch.records import (
    AgentRecord,
    Outcome,
    SecurityEvent,
    SecurityEventType,
    effective_authorization,
)
from agentwatch.store import RecordStore

OVERSIGHT_VERSION = "oversight-v1"

BY_OPTIONS = ("source", "day", "user", "mode", "tool-class")

# cls1 classes that matter to the oversight cross-tab (PRD 33 cls1).
CROSS_TAB_CLASSES: tuple[str, ...] = (CMD_DESTRUCTIVE, NETWORK, CREDENTIAL)

PROMPT_TOOL = "permission-prompt"

# Synthetic sessions the recorder authors; not agent work.
_INTERNAL_SESSIONS = frozenset({"agentwatch", "external"})


@dataclass(frozen=True)
class SourceRow:
    """Calls attributed to one authorization source."""

    source: str
    calls: int
    share: float | None
    destructive: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "calls": self.calls,
            "share": self.share,
            "destructive": self.destructive,
        }


@dataclass(frozen=True)
class CrossTabCell:
    """One ``cls1 class × authorization source`` cell of the incident cross-tab."""

    tool_class: str
    source: str
    calls: int

    def to_dict(self) -> dict[str, Any]:
        return {"tool_class": self.tool_class, "source": self.source, "calls": self.calls}


@dataclass(frozen=True)
class SessionMode:
    """The mode a session started and ended under."""

    session_id: str
    start_mode: str
    end_mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "start_mode": self.start_mode,
            "end_mode": self.end_mode,
        }


@dataclass(frozen=True)
class DecisionLatency:
    """Time-to-decision distribution for paired prompts/decisions."""

    decisions: int
    with_timestamps: int
    median_ms: float | None
    sub_second_fraction: float | None
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisions": self.decisions,
            "with_timestamps": self.with_timestamps,
            "median_ms": self.median_ms,
            "sub_second_fraction": self.sub_second_fraction,
            "note": self.note,
        }


@dataclass(frozen=True)
class HumanOversight:
    """Human-prompted calls: approve/reject rate and decision latency."""

    prompted: int
    approved: int
    rejected: int
    approve_rate: float | None
    reject_rate: float | None
    latency: DecisionLatency

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompted": self.prompted,
            "approved": self.approved,
            "rejected": self.rejected,
            "approve_rate": self.approve_rate,
            "reject_rate": self.reject_rate,
            "latency": self.latency.to_dict(),
        }


@dataclass(frozen=True)
class SandboxFacts:
    """Sandbox-boundary facts: how many calls ran outside it, and denials.

    ``calls_with_fact`` is the denominator: calls that actually carried a sandbox
    signal. Calls with no signal are counted ``unknown`` and are **not** treated
    as unsandboxed (never inferred from absence).
    """

    calls_with_fact: int
    sandboxed: int
    unsandboxed: int
    unknown: int
    unsandboxed_share: float | None
    denials: int
    denials_by_class: tuple[tuple[str, int], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_with_fact": self.calls_with_fact,
            "sandboxed": self.sandboxed,
            "unsandboxed": self.unsandboxed,
            "unknown": self.unknown,
            "unsandboxed_share": self.unsandboxed_share,
            "denials": self.denials,
            "denials_by_class": dict(self.denials_by_class),
        }


@dataclass(frozen=True)
class SandboxExposure:
    """Per-harness sandbox-signal exposure, declared honestly."""

    harness: str
    status: str
    note: str


# Signal availability verified per harness (M30 SBX-1): Claude Code's OTel
# vocabulary (CCO-1) has no sandbox event; Cursor's raw before/afterShellExecution
# payload carries `sandbox`, but the Cursor adapter does not preserve it yet.
SANDBOX_EXPOSURE: tuple[SandboxExposure, ...] = (
    SandboxExposure(
        "claude-code",
        COVERAGE_NONE,
        "the CCO-1 OTel vocabulary exposes no sandbox event",
    ),
    SandboxExposure(
        "cursor",
        COVERAGE_PARTIAL,
        "raw before/afterShellExecution carries sandbox; adapter capture is a "
        "harness-adapter follow-up",
    ),
    SandboxExposure("codex-cli", COVERAGE_NONE, "no sandbox signal exposed"),
    SandboxExposure("gemini-cli", COVERAGE_NONE, "no sandbox signal exposed"),
)


def sandbox_exposure_matrix() -> tuple[SandboxExposure, ...]:
    """The published, CI-checked sandbox-exposure matrix (one row per harness)."""
    return SANDBOX_EXPOSURE


def sandbox_boundary_event(
    *,
    tool: str,
    sandboxed: bool,
    emitted_at: datetime,
    denied_destination: str | None = None,
) -> SecurityEvent:
    """A ``sandbox-boundary`` observation (never enforcement)."""
    evidence: dict[str, Any] = {"tool": tool, "sandboxed": sandboxed}
    if denied_destination is not None:
        evidence["denied_destination"] = denied_destination
    return SecurityEvent(
        type=SecurityEventType.SANDBOX_BOUNDARY,
        emitted_at=emitted_at,
        emitter="agentwatch",
        tool=tool,
        evidence=evidence,
    )


@dataclass(frozen=True)
class GroupRow:
    """One ``--by`` bucket and its authorization mix."""

    key: str
    calls: int
    sources: tuple[tuple[str, int], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "calls": self.calls, "sources": dict(self.sources)}


@dataclass(frozen=True)
class OversightReport:
    """The whole oversight report (facts only, version-stamped)."""

    generated_at: datetime
    total_calls: int
    since: str | None = None
    project: str | None = None
    grouped_by: str = "source"
    taxonomy_version: str = AUTHORIZATION_TAXONOMY_VERSION
    classifier_version: str = "cls1"
    sources: tuple[SourceRow, ...] = ()
    sessions_by_mode: tuple[SessionMode, ...] = ()
    human: HumanOversight | None = None
    cross_tab: tuple[CrossTabCell, ...] = ()
    destructive_total: int = 0
    groups: tuple[GroupRow, ...] = ()
    sandbox: SandboxFacts | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "oversight_version": OVERSIGHT_VERSION,
            "generated_at": self.generated_at.isoformat(),
            "since": self.since,
            "project": self.project,
            "grouped_by": self.grouped_by,
            "taxonomy_version": self.taxonomy_version,
            "classifier_version": self.classifier_version,
            "total_calls": self.total_calls,
            "destructive_total": self.destructive_total,
            "sources": [row.to_dict() for row in self.sources],
            "sessions_by_mode": [session.to_dict() for session in self.sessions_by_mode],
            "human": self.human.to_dict() if self.human is not None else None,
            "cross_tab": [cell.to_dict() for cell in self.cross_tab],
            "groups": [group.to_dict() for group in self.groups],
            "sandbox": self.sandbox.to_dict() if self.sandbox is not None else None,
            "note": self.note,
        }


def _destructive_classes(record: AgentRecord) -> tuple[str, ...]:
    facts = classify_record(record)
    return tuple(
        sorted({fact.category for fact in facts if fact.category in CROSS_TAB_CLASSES})
    )


def _primary_class(record: AgentRecord) -> str:
    facts = classify_record(record)
    for fact in facts:
        if fact.category != UNCLASSIFIED:
            return fact.category
    return UNCLASSIFIED


def _group_key(by: str, record: AgentRecord, modes: dict[int, str]) -> str:
    if by == "day":
        return record.started_at.date().isoformat()
    if by == "user":
        return record.agent.principal or record.agent.identity
    if by == "mode":
        return modes.get(id(record), "unknown")
    if by == "tool-class":
        return _primary_class(record)
    return effective_authorization(record).source.value


def _latency(pairs: list[tuple[AgentRecord, AgentRecord]]) -> DecisionLatency:
    values = [
        (decision.started_at - prompt.started_at).total_seconds() * 1000
        for prompt, decision in pairs
        if prompt.started_at is not None and decision.started_at is not None
    ]
    values = [value for value in values if value >= 0]
    if not values:
        return DecisionLatency(
            0, 0, None, None, f"n/a ({len(pairs)} calls without paired timestamps)"
        )
    sub_second = sum(1 for value in values if value < 1000) / len(values)
    return DecisionLatency(
        decisions=len(values),
        with_timestamps=len(values),
        median_ms=round(float(median(values)), 3),
        sub_second_fraction=sub_second,
        note=f"{len(values)} decision(s) with paired timestamps",
    )


def build_oversight(
    store: RecordStore,
    *,
    since: str | None = None,
    project: str | None = None,
    by: str = "source",
    now: datetime | None = None,
) -> OversightReport:
    """Build the offline oversight report for the selected scope."""
    if by not in BY_OPTIONS:
        raise ValueError(f"unknown --by value {by!r}; expected one of {', '.join(BY_OPTIONS)}")
    moment = now or datetime.now(timezone.utc)
    cutoff = since_cutoff(since, now=moment) if since is not None else None
    records = [
        record
        for record in store.records()
        if record.session_id not in _INTERNAL_SESSIONS
        and (cutoff is None or record.started_at >= cutoff)
        and (project is None or record.project == project)
    ]
    calls = [record for record in records if is_tool_call_record(record)]
    mode_records = [
        record
        for record in records
        if is_tool_call_record(record) or is_permission_mode_change(record)
    ]
    modes = {record_id: mode.value for record_id, mode in effective_modes(mode_records).items()}

    total = len(calls)
    source_counts: dict[str, int] = {}
    destructive_by_source: dict[str, int] = {}
    cross: dict[tuple[str, str], int] = {}
    destructive_total = 0
    for record in calls:
        source = effective_authorization(record).source.value
        source_counts[source] = source_counts.get(source, 0) + 1
        classes = _destructive_classes(record)
        if classes:
            destructive_total += 1
            destructive_by_source[source] = destructive_by_source.get(source, 0) + 1
            for tool_class in classes:
                cross[(tool_class, source)] = cross.get((tool_class, source), 0) + 1

    sources = tuple(
        SourceRow(
            source=source,
            calls=count,
            share=(count / total) if total else None,
            destructive=destructive_by_source.get(source, 0),
        )
        for source, count in sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))
    )
    cross_tab = tuple(
        CrossTabCell(tool_class, source, count)
        for (tool_class, source), count in sorted(cross.items())
    )

    # Sessions by starting/ending mode.
    sessions: list[SessionMode] = []
    for session_id in sorted({record.session_id for record in calls}):
        scoped = [record for record in mode_records if record.session_id == session_id]
        intervals = mode_intervals(scoped)
        if intervals:
            sessions.append(
                SessionMode(session_id, intervals[0].mode.value, intervals[-1].mode.value)
            )
        else:
            sessions.append(SessionMode(session_id, "unknown", "unknown"))

    # Human oversight: pair permission prompts to their decision by span_id.
    prompts: dict[str, AgentRecord] = {
        record.span_id: record
        for record in records
        if record.tool.name == PROMPT_TOOL and record.span_id is not None
    }
    pairs: list[tuple[AgentRecord, AgentRecord]] = []
    approved = 0
    rejected = 0
    for record in calls:
        prompt = prompts.get(record.span_id or "")
        if prompt is None:
            continue
        pairs.append((prompt, record))
        if record.outcome is Outcome.DENIED:
            rejected += 1
        else:
            approved += 1
    prompted = len(pairs)
    human = HumanOversight(
        prompted=prompted,
        approved=approved,
        rejected=rejected,
        approve_rate=(approved / prompted) if prompted else None,
        reject_rate=(rejected / prompted) if prompted else None,
        latency=_latency(pairs),
    )

    # `--by` grouping over the calls.
    grouped: dict[str, dict[str, int]] = {}
    for record in calls:
        key = _group_key(by, record, modes)
        bucket = grouped.setdefault(key, {})
        source = effective_authorization(record).source.value
        bucket[source] = bucket.get(source, 0) + 1
    groups = tuple(
        GroupRow(
            key=key,
            calls=sum(bucket.values()),
            sources=tuple(sorted(bucket.items())),
        )
        for key, bucket in sorted(grouped.items())
    )

    # Sandbox-boundary facts (M30 SBX-1). A missing signal is `unknown`, never
    # counted as unsandboxed; the share denominator is calls that carried a fact.
    sandboxed = unsandboxed = unknown = 0
    denials = 0
    denial_classes: dict[str, int] = {}
    for record in calls:
        if record.sandbox is True:
            sandboxed += 1
        elif record.sandbox is False:
            unsandboxed += 1
        else:
            unknown += 1
        if record.outcome is Outcome.DENIED:
            denials += 1
            for fact in classify_record(record):
                if fact.category != UNCLASSIFIED:
                    denial_classes[fact.category] = denial_classes.get(fact.category, 0) + 1
    with_fact = sandboxed + unsandboxed
    sandbox = SandboxFacts(
        calls_with_fact=with_fact,
        sandboxed=sandboxed,
        unsandboxed=unsandboxed,
        unknown=unknown,
        unsandboxed_share=(unsandboxed / with_fact) if with_fact else None,
        denials=denials,
        denials_by_class=tuple(sorted(denial_classes.items())),
    )

    note = None if total else "no agent tool calls in the window"
    return OversightReport(
        generated_at=moment,
        total_calls=total,
        since=since,
        project=project,
        grouped_by=by,
        sources=sources,
        sessions_by_mode=tuple(sessions),
        human=human,
        cross_tab=cross_tab,
        destructive_total=destructive_total,
        groups=groups,
        sandbox=sandbox,
        note=note,
    )


def _ratio(numerator: int | None, denominator: int | None) -> str:
    if not denominator or numerator is None:
        return "n/a (0 calls)"
    return f"{numerator}/{denominator} ({numerator / denominator * 100:.1f}%)"


def render_oversight(report: OversightReport) -> str:
    """Render the report as facts with denominators (never a score)."""
    lines = [
        f"agentwatch oversight (taxonomy {report.taxonomy_version}, "
        f"classifier {report.classifier_version}, {OVERSIGHT_VERSION})",
        f"  generated: {report.generated_at.isoformat()}"
        + (f", since {report.since}" if report.since else "")
        + (f", project {report.project}" if report.project else ""),
        f"  calls: {report.total_calls}",
        "",
        "authorization mix (share of all calls):",
    ]
    if report.sources:
        for row in report.sources:
            share = f"{row.share * 100:.1f}%" if row.share is not None else "n/a"
            lines.append(
                f"    {row.source}: {row.calls} ({share}); destructive-class {row.destructive}"
            )
    else:
        lines.append("    none")
    lines.append("")
    lines.append("sessions by mode (start -> end):")
    for session in report.sessions_by_mode:
        lines.append(f"    {session.session_id}: {session.start_mode} -> {session.end_mode}")
    if report.human is not None:
        lines.append("")
        lines.append("human-prompted calls:")
        lines.append(
            f"    approve: {_ratio(report.human.approved, report.human.prompted)}; "
            f"reject: {_ratio(report.human.rejected, report.human.prompted)}"
        )
        latency = report.human.latency
        median_ms = latency.median_ms
        if median_ms is None:
            lines.append(f"    time-to-decision: {latency.note}")
        else:
            fraction = latency.sub_second_fraction or 0.0
            lines.append(
                f"    time-to-decision: median {median_ms:.0f}ms; "
                f"sub-second {fraction * 100:.1f}% "
                f"({latency.decisions} decision(s))"
            )
    lines.append("")
    lines.append(
        f"destructive/network/credential-adjacent x authorization "
        f"({report.destructive_total} call(s)):"
    )
    if report.cross_tab:
        for cell in report.cross_tab:
            lines.append(f"    {cell.tool_class} × {cell.source}: {cell.calls}")
    else:
        lines.append("    none")
    if report.sandbox is not None:
        sandbox = report.sandbox
        lines.append("")
        share = (
            f"{sandbox.unsandboxed_share * 100:.1f}%"
            if sandbox.unsandboxed_share is not None
            else "n/a (0 calls with a sandbox fact)"
        )
        lines.append(
            f"sandbox boundary: % calls unsandboxed {sandbox.unsandboxed}/"
            f"{sandbox.calls_with_fact} ({share}); "
            f"unknown signal {sandbox.unknown}; denials {sandbox.denials}"
        )
        for tool_class, count in sandbox.denials_by_class:
            lines.append(f"    denied {tool_class}: {count}")
    lines.append("")
    lines.append(f"grouped by {report.grouped_by}:")
    for group in report.groups:
        mix = ", ".join(f"{source}={count}" for source, count in group.sources)
        lines.append(f"    {group.key}: {group.calls} ({mix})")
    if report.note:
        lines.append(f"  note: {report.note}")
    return "\n".join(lines)


__all__ = [
    "BY_OPTIONS",
    "CROSS_TAB_CLASSES",
    "SANDBOX_EXPOSURE",
    "CrossTabCell",
    "DecisionLatency",
    "GroupRow",
    "HumanOversight",
    "OVERSIGHT_VERSION",
    "OversightReport",
    "SandboxExposure",
    "SandboxFacts",
    "SessionMode",
    "SourceRow",
    "build_oversight",
    "render_oversight",
    "sandbox_boundary_event",
    "sandbox_exposure_matrix",
]
