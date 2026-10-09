"""``agentwatch coverage`` — reconcile the store against ground truth (M16 S2, #238).

``verify-store`` answers *intact?* and ``verify-privacy`` answers *leak-free?*;
nothing answered *complete?*. This module counts the tool calls an independent
ground truth (the Claude Code transcript) says happened, compares them to the
distinct tool calls in the store, and classifies every discrepancy by cause:

``gap:daemon-down``, ``gap:quarantined``, ``gap:trust-gated-headless``,
``gap:hook-not-installed``, ``gap:transcript-format-drift``,
``gap:harness-drift`` (S19), or ``gap:unexplained``.

``gap:unexplained`` should be zero on a clean fixture. The transcript is read
through the A5 allow-list extractor (:mod:`agentwatch.transcript`), so only counts
and tool names — never content — are read.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from agentwatch.attestation import attestation_status
from agentwatch.claude_otel import NON_TOOL_EVENTS, otel_join_summary
from agentwatch.harness_drift import harness_drift_observations
from agentwatch.permission_mode import effective_modes
from agentwatch.quarantine import QuarantineLog
from agentwatch.recorder_state import CoverageWindow, coverage_windows
from agentwatch.records import (
    AgentRecord,
    PermissionMode,
    ProducerKind,
    StepType,
    _parse_iso,
    effective_producer,
)
from agentwatch.store import RecordStore
from agentwatch.transcript import extract_tool_calls

CAUSE_DAEMON_DOWN = "gap:daemon-down"
CAUSE_QUARANTINED = "gap:quarantined"
CAUSE_TRUST_GATED = "gap:trust-gated-headless"
CAUSE_HOOK_NOT_INSTALLED = "gap:hook-not-installed"
CAUSE_TRANSCRIPT_DRIFT = "gap:transcript-format-drift"
CAUSE_HARNESS_DRIFT = "gap:harness-drift"
CAUSE_CURSOR_HOOK_COVERAGE = "gap:cursor-hook-coverage"
CAUSE_UNEXPLAINED = "gap:unexplained"

CAUSES = (
    CAUSE_DAEMON_DOWN,
    CAUSE_QUARANTINED,
    CAUSE_TRUST_GATED,
    CAUSE_HOOK_NOT_INSTALLED,
    CAUSE_TRANSCRIPT_DRIFT,
    CAUSE_HARNESS_DRIFT,
    CAUSE_CURSOR_HOOK_COVERAGE,
    CAUSE_UNEXPLAINED,
)

RECORDING_GAP_TOOL = "recording-gap"
HOOK_ERROR_TOOL = "hook-error"

# Synthetic sessions the recorder authors; they are not agent work.
INTERNAL_SESSIONS = frozenset({"agentwatch", "external"})

# Records that are not a tool call (markers, boundaries, usage, drift).
_NON_TOOL_NAMES = frozenset(
    {
        RECORDING_GAP_TOOL,
        HOOK_ERROR_TOOL,
        "session-purge",
        "operator-note",
        "store-access",
        "key-rotation",
        "harness-drift",
        "recorder-installed",
        "recorder-uninstalled",
        "config-changed",
        "privacy-mode-changed",
        "retention-changed",
        "export-configured",
        "coverage-window-open",
        "coverage-window-close",
        "session-usage",
        "external-event",
        "context-compacted",
        "permission-prompt",
    }
    | set(NON_TOOL_EVENTS)
)


@dataclass(frozen=True)
class TranscriptCoverage:
    """Tool-call ground truth for one session (counts and names only)."""

    session_id: str
    tool_calls: int
    tools: tuple[str, ...] = ()
    malformed: int = 0
    last_at: datetime | None = None


@dataclass(frozen=True)
class GapFinding:
    """One classified discrepancy."""

    cause: str
    count: int
    detail: str


@dataclass(frozen=True)
class SessionCoverage:
    """Reconciliation for one session."""

    session_id: str
    project: str | None
    transcript_calls: int
    store_calls: int
    unknown: bool
    capture_rate: float | None
    gaps: tuple[GapFinding, ...] = ()

    @property
    def unexplained(self) -> int:
        return sum(g.count for g in self.gaps if g.cause == CAUSE_UNEXPLAINED)


@dataclass(frozen=True)
class CoverageReport:
    """The whole reconciliation: sessions, coverage windows, totals."""

    transcripts_present: bool
    sessions: tuple[SessionCoverage, ...] = ()
    windows: tuple[CoverageWindow, ...] = ()
    since: str | None = None
    totals: dict[str, Any] = field(default_factory=dict)
    attestation: str | None = None
    otel_join: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "transcripts_present": self.transcripts_present,
            "since": self.since,
            "attestation": self.attestation,
            "otel_join": self.otel_join,
            "sessions": [
                {
                    "session_id": s.session_id,
                    "project": s.project,
                    "transcript_calls": s.transcript_calls,
                    "store_calls": s.store_calls,
                    "capture_rate": s.capture_rate,
                    "unknown": s.unknown,
                    "gaps": [
                        {"cause": g.cause, "count": g.count, "detail": g.detail} for g in s.gaps
                    ],
                }
                for s in self.sessions
            ],
            "windows": [
                {
                    "open_seq": w.open_seq,
                    "opened_at": w.opened_at.isoformat(),
                    "reason": w.reason,
                    "close_seq": w.close_seq,
                    "closed_at": w.closed_at.isoformat() if w.closed_at else None,
                    "active": w.active,
                }
                for w in self.windows
            ],
            "totals": dict(self.totals),
        }

    def render(self) -> str:
        lines: list[str] = ["agentwatch coverage"]
        if not self.transcripts_present:
            lines.append("  transcripts: not present; coverage unknown for this period")
        for session in self.sessions:
            if session.unknown:
                rate = "unknown"
            elif session.capture_rate is None:
                rate = "n/a"
            else:
                rate = f"{session.capture_rate * 100:.1f}%"
            lines.append(
                f"  {session.session_id}: {session.store_calls}/{session.transcript_calls} "
                f"calls, capture {rate}"
            )
            for gap in session.gaps:
                lines.append(f"    {gap.cause} x{gap.count}: {gap.detail}")
        totals = self.totals
        lines.append(
            f"  totals: {totals.get('store_calls', 0)}/{totals.get('transcript_calls', 0)} calls, "
            f"unexplained {totals.get('unexplained', 0)}"
        )
        if totals.get("mode_unknown"):
            lines.append(
                f"  permission mode: {totals.get('mode_known', 0)} known, "
                f"{totals['mode_unknown']} unknown"
            )
        if self.otel_join is not None:
            lines.append(f"  native telemetry join: {self.otel_join}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Ground truth (transcripts)
# ---------------------------------------------------------------------------


def discover_transcripts(
    base: Path | str, *, since: datetime | None = None
) -> tuple[dict[str, TranscriptCoverage], bool]:
    """Scan a transcript directory, returning per-session coverage and "present".

    ``present`` is False when the directory does not exist: coverage is then
    *unknown for the period*, never 100% (edge case in PRD 32 S2).
    """
    base_path = Path(base).expanduser()
    if not base_path.is_dir():
        return {}, False
    sessions: dict[str, TranscriptCoverage] = {}
    for path in sorted(base_path.rglob("*.jsonl")):
        summary = extract_tool_calls(path)
        if summary.session_id is None:
            continue
        last_at: datetime | None = None
        if summary.last_at is not None:
            try:
                last_at = _parse_iso(summary.last_at)
            except ValueError:
                last_at = None
        if since is not None and last_at is not None and last_at < since:
            continue
        existing = sessions.get(summary.session_id)
        if existing is None:
            sessions[summary.session_id] = TranscriptCoverage(
                session_id=summary.session_id,
                tool_calls=summary.tool_calls,
                tools=summary.tools,
                malformed=summary.malformed,
                last_at=last_at,
            )
        else:
            sessions[summary.session_id] = TranscriptCoverage(
                session_id=summary.session_id,
                tool_calls=existing.tool_calls + summary.tool_calls,
                tools=tuple(sorted({*existing.tools, *summary.tools})),
                malformed=existing.malformed + summary.malformed,
                last_at=_latest(existing.last_at, last_at),
            )
    return sessions, True


def _cursor_tool_calls(trace: Mapping[str, Any]) -> int:
    """Ground-truth tool-call count from a Cursor session-tracer trace.

    Prefer the trace's own ``cursor_stats.tool_call_count``; otherwise count the
    structural file operations (reads + writes) the trace records.
    """
    session = trace.get("session")
    if isinstance(session, Mapping):
        stats = session.get("cursor_stats")
        if isinstance(stats, Mapping):
            stated = stats.get("tool_call_count")
            if isinstance(stated, int) and stated >= 0:
                return stated
    calls = 0
    events = trace.get("events")
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, Mapping):
                continue
            reads = event.get("files_read")
            calls += len(reads) if isinstance(reads, list) else 0
            if event.get("type") in ("file_create", "file_modify", "file_delete"):
                calls += 1
    return calls


def extract_cursor_trace(path: Path | str) -> TranscriptCoverage | None:
    """Read one Cursor session-tracer trace as ground truth (counts only).

    Returns ``None`` when the trace has no session id (no ground truth to anchor
    to), so a malformed trace is skipped rather than mis-attributed.
    """
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    session = payload.get("session")
    if not isinstance(session, Mapping):
        return None
    session_id = session.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return None
    tools: set[str] = set()
    events = payload.get("events")
    if isinstance(events, list):
        for event in events:
            if isinstance(event, Mapping):
                kind = event.get("type")
                if isinstance(kind, str):
                    tools.add(str(kind))
    return TranscriptCoverage(
        session_id=session_id,
        tool_calls=_cursor_tool_calls(payload),
        tools=tuple(sorted(tools)),
    )


def discover_cursor_transcripts(
    base: Path | str, *, since: datetime | None = None
) -> tuple[dict[str, TranscriptCoverage], bool]:
    """Scan a Cursor session-tracer directory for per-session ground truth.

    ``present`` is False when the directory does not exist (coverage is then
    unknown, never 100%).
    """
    base_path = Path(base).expanduser()
    if not base_path.is_dir():
        return {}, False
    sessions: dict[str, TranscriptCoverage] = {}
    for path in sorted(base_path.rglob("*.json")):
        if path.name == "manifest.json":
            continue
        extracted = extract_cursor_trace(path)
        if extracted is None:
            continue
        sessions[extracted.session_id] = extracted
    return sessions, True


# ---------------------------------------------------------------------------
# Store evidence
# ---------------------------------------------------------------------------


def is_tool_call_record(record: AgentRecord) -> bool:
    """Whether a record is an agent tool call (not a marker/boundary/usage).

    Demo records (``producer.kind: demo``) are synthetic and never count as
    coverage of real agent work (M19 S31).
    """
    if effective_producer(record).kind is ProducerKind.DEMO:
        return False
    if record.tool.name in _NON_TOOL_NAMES:
        return False
    if record.harness is None:
        return False
    return record.step_type in (StepType.ACT, StepType.OBSERVE)


def store_tool_calls(
    records: Iterable[AgentRecord],
) -> tuple[dict[str, int], dict[str, str | None]]:
    """Distinct tool calls per session (a pre/post pair shares a span -> one).

    Returns ``(counts, projects)``.
    """
    keys: dict[str, set[str]] = {}
    projects: dict[str, str | None] = {}
    counters: dict[str, int] = {}
    for record in records:
        if not is_tool_call_record(record):
            continue
        session = record.session_id
        if record.project is not None and session not in projects:
            projects[session] = record.project
        bucket = keys.setdefault(session, set())
        if record.span_id is not None:
            bucket.add("span:" + record.span_id)
        else:
            counter = counters.get(session, 0)
            counters[session] = counter + 1
            bucket.add(f"anon:{counter}")
    return {session: len(bucket) for session, bucket in keys.items()}, projects


def _evidence_counts(store: RecordStore) -> dict[str, dict[str, int]]:
    """Per-session counts of gap-producing records (gap/hook-error)."""
    counts: dict[str, dict[str, int]] = {}
    for record in store.records():
        bucket = counts.setdefault(record.session_id, {"gap": 0, "hook_error": 0, "drift": 0})
        if record.tool.name == RECORDING_GAP_TOOL:
            bucket["gap"] += 1
        elif record.tool.name == HOOK_ERROR_TOOL:
            bucket["hook_error"] += 1
    for observation in harness_drift_observations(store):
        counts.setdefault(observation.session_id, {"gap": 0, "hook_error": 0, "drift": 0})[
            "drift"
        ] += 1
    return counts


def quarantine_counts(quarantine: QuarantineLog | None) -> dict[str | None, int]:
    """Count quarantined frames per session by reading the raw frame's *metadata*."""
    if quarantine is None or not quarantine.path.exists():
        return {}
    result: dict[str | None, int] = {}
    for entry in quarantine.entries():
        session = _raw_session(entry.get("raw"))
        result[session] = result.get(session, 0) + 1
    return result


def _latest(a: datetime | None, b: datetime | None) -> datetime | None:
    if a is None:
        return b
    if b is None:
        return a
    return a if a >= b else b


def _raw_session(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, Mapping):
        return None
    for source in (payload, payload.get("event")):
        if isinstance(source, Mapping):
            for key in ("session_id", "sessionId"):
                value = source.get(key)
                if isinstance(value, str) and value:
                    return value
    return None


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


def classify_session(
    session_id: str,
    *,
    project: str | None,
    transcript: TranscriptCoverage | None,
    store_calls: int,
    hooks_installed: bool,
    gap_count: int,
    hook_error_count: int,
    drift_count: int,
    quarantine_count: int,
    harness: str | None = None,
) -> SessionCoverage:
    """Classify one session's discrepancy by cause (a clean session has none)."""
    if transcript is None:
        return SessionCoverage(
            session_id=session_id,
            project=project,
            transcript_calls=0,
            store_calls=store_calls,
            unknown=True,
            capture_rate=None,
        )
    calls = transcript.tool_calls
    missing = max(0, calls - store_calls)
    gaps: list[GapFinding] = []
    if missing:
        if gap_count or hook_error_count:
            detail = f"{gap_count} recording-gap, {hook_error_count} hook-error record(s)"
            gaps.append(GapFinding(CAUSE_DAEMON_DOWN, missing, detail))
        elif quarantine_count:
            gaps.append(
                GapFinding(CAUSE_QUARANTINED, missing, f"{quarantine_count} quarantined frame(s)")
            )
        elif not hooks_installed:
            gaps.append(GapFinding(CAUSE_HOOK_NOT_INSTALLED, missing, "hooks not installed"))
        elif transcript.malformed:
            gaps.append(
                GapFinding(
                    CAUSE_TRANSCRIPT_DRIFT, missing, f"{transcript.malformed} malformed line(s)"
                )
            )
        elif drift_count:
            gaps.append(
                GapFinding(CAUSE_HARNESS_DRIFT, missing, f"{drift_count} drift observation(s)")
            )
        elif harness == "cursor":
            # Cursor's hook surface is phase-gated (IDE vs cloud/Tab); a shortfall
            # is a declared capture gap, not an unexplained one (CUR-3).
            gaps.append(
                GapFinding(
                    CAUSE_CURSOR_HOOK_COVERAGE,
                    missing,
                    "Cursor hook surface incomplete (IDE/cloud phases not captured)",
                )
            )
        elif store_calls == 0:
            # Hooks are installed, the store is empty, but the transcript is not:
            # the documented cause is headless workspace-trust suppression.
            gaps.append(
                GapFinding(CAUSE_TRUST_GATED, missing, "project hooks suppressed in a headless run")
            )
        else:
            gaps.append(GapFinding(CAUSE_UNEXPLAINED, missing, "no cause identified"))
    rate = (store_calls / calls) if calls else None
    return SessionCoverage(
        session_id=session_id,
        project=project,
        transcript_calls=calls,
        store_calls=store_calls,
        unknown=False,
        capture_rate=rate,
        gaps=tuple(gaps),
    )


def build_coverage(
    store: RecordStore,
    *,
    transcripts: Mapping[str, TranscriptCoverage],
    transcripts_present: bool = True,
    since: str | None = None,
    project: str | None = None,
    session: str | None = None,
    hooks_installed: bool = True,
    quarantine: QuarantineLog | None = None,
    now: datetime | None = None,
) -> CoverageReport:
    """Reconcile the store against transcript ground truth for the selected scope."""
    from agentwatch.query import since_cutoff

    cutoff = since_cutoff(since, now=now) if since is not None else None
    records = [
        record for record in store.records() if cutoff is None or record.started_at >= cutoff
    ]
    counts, projects = store_tool_calls(records)
    harness_by_session: dict[str, str] = {}
    for record in records:
        if record.harness is not None and record.session_id not in harness_by_session:
            harness_by_session[record.session_id] = record.harness
    evidence = _evidence_counts(store)
    quarantined = quarantine_counts(quarantine)

    selected: set[str] = set(counts) | {
        sid for sid in transcripts if session is None or sid == session
    }
    if session is not None:
        selected = {session}
    selected.discard("agentwatch")
    selected.discard("external")
    if project is not None:
        selected = {sid for sid in selected if projects.get(sid) == project}

    sessions: list[SessionCoverage] = []
    for sid in sorted(selected):
        transcript = transcripts.get(sid)
        if transcript is None and not transcripts_present:
            transcript = None
        sessions.append(
            classify_session(
                sid,
                project=projects.get(sid),
                transcript=transcript,
                store_calls=counts.get(sid, 0),
                hooks_installed=hooks_installed,
                gap_count=evidence.get(sid, {}).get("gap", 0),
                hook_error_count=evidence.get(sid, {}).get("hook_error", 0),
                drift_count=evidence.get(sid, {}).get("drift", 0),
                quarantine_count=quarantined.get(sid, 0) + quarantined.get(None, 0),
                harness=harness_by_session.get(sid),
            )
        )

    known = [s for s in sessions if not s.unknown]
    transcript_total = sum(s.transcript_calls for s in known)
    store_total = sum(s.store_calls for s in known)
    rate = (store_total / transcript_total) if transcript_total else None
    modes = effective_modes(records)
    tool_records = [record for record in records if is_tool_call_record(record)]
    mode_known = sum(
        1
        for record in tool_records
        if modes.get(id(record), PermissionMode.UNKNOWN) is not PermissionMode.UNKNOWN
    )
    totals: dict[str, Any] = {
        "sessions": len(sessions),
        "known_sessions": len(known),
        "transcript_calls": transcript_total,
        "store_calls": store_total,
        "capture_rate": rate,
        "mode_known": mode_known,
        "mode_unknown": len(tool_records) - mode_known,
        "unexplained": sum(s.unexplained for s in sessions),
        "gaps": {
            cause: sum(g.count for s in sessions for g in s.gaps if g.cause == cause)
            for cause in CAUSES
        },
    }
    return CoverageReport(
        transcripts_present=transcripts_present,
        sessions=tuple(sessions),
        windows=tuple(coverage_windows(store)),
        since=since,
        totals=totals,
        otel_join=otel_join_summary(records),
        attestation=attestation_status(store),
    )


def default_transcript_base() -> Path:
    """Claude Code's default transcript root."""
    return Path.home() / ".claude" / "projects"
