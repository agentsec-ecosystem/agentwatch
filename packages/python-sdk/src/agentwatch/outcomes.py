"""Deterministic outcome facts (M30 OUT-1, PRD 58).

Leaders ask for cost per *shipped* change, not per session. agentwatch answers
with **facts, not a quality score**: command outcomes (test / build / lint),
retained vs reverted changes, interruptions/rejections, and retries to success —
each a ratio or count with a numerator, a denominator, and a **derivation
version**. There is no LLM and no network in this path; unknown stays unknown.

The design is published in docs/design/outcomes-signals.md.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from agentwatch.query import since_cutoff
from agentwatch.records import AgentRecord, SecurityEventType, effective_authorization
from agentwatch.store import RecordStore

# Bumped when the derivation semantics change; rides in every output so a
# consumer can branch on it. Never a "score".
OUTCOME_DERIVATION_VERSION = "out1"

BY_OPTIONS = ("session", "project", "model", "harness")
NO_KEY = "(none)"
UNKNOWN_MODEL = "(unknown)"

_FILE_CATEGORIES = frozenset({"file:write", "file:edit", "file:delete"})

# A deterministic, published extension over cls1 for command outcomes. A command
# is a test/build/lint command by token; the outcome class is the record outcome.
OUTCOME_RULES_VERSION = "cls2-out1"
COMMAND_CLASS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "test",
        re.compile(
            r"\b(pytest|jest|vitest|mocha|rspec|go test|cargo test|"
            r"npm test|pnpm test|yarn test)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "build",
        re.compile(
            r"\b(make|cmake|cargo build|go build|npm run build|pnpm build|"
            r"yarn build|tsc|mvn|gradle|bazel build|docker build)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "lint",
        re.compile(
            r"\b(ruff|flake8|pylint|mypy|eslint|black --check|prettier --check|"
            r"golangci-lint|clippy)\b",
            re.IGNORECASE,
        ),
    ),
)

_REVERT_RE = re.compile(
    r"\bgit\s+(?:reset\s+--hard|checkout\s+--|revert|clean\s+-[a-z]*f)\b",
    re.IGNORECASE,
)
_INTERRUPT_EVENTS = frozenset({SecurityEventType.HALTED.value, SecurityEventType.REVOKED.value})


@dataclass(frozen=True)
class Ratio:
    """A fact with a numerator and denominator; ``value`` is unknown at 0/0."""

    numerator: int
    denominator: int

    @property
    def value(self) -> float | None:
        return self.numerator / self.denominator if self.denominator else None

    def to_dict(self) -> dict[str, object]:
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "value": self.value,
        }


@dataclass(frozen=True)
class OutcomeRow:
    """Outcome facts for one rollup bucket."""

    key: str
    sessions: int = 0
    test_pass: Ratio = Ratio(0, 0)
    build_pass: Ratio = Ratio(0, 0)
    lint_pass: Ratio = Ratio(0, 0)
    retained: int = 0
    reverted: int = 0
    interrupted: int = 0
    rejected: int = 0
    retries_to_success: int = 0
    retained_known: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "sessions": self.sessions,
            "test_pass": self.test_pass.to_dict(),
            "build_pass": self.build_pass.to_dict(),
            "lint_pass": self.lint_pass.to_dict(),
            "retained": self.retained,
            "retained_known": self.retained_known,
            "reverted": self.reverted,
            "interrupted": self.interrupted,
            "rejected": self.rejected,
            "retries_to_success": self.retries_to_success,
        }


@dataclass(frozen=True)
class OutcomeReport:
    """A deterministic outcome rollup with its derivation version."""

    by: str = "project"
    since: str | None = None
    derivation_version: str = OUTCOME_DERIVATION_VERSION
    rules_version: str = OUTCOME_RULES_VERSION
    rows: tuple[OutcomeRow, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "by": self.by,
            "since": self.since,
            "derivation_version": self.derivation_version,
            "rules_version": self.rules_version,
            "rows": [row.to_dict() for row in self.rows],
            "notes": list(self.notes),
        }


def command_classes(command: str) -> tuple[str, ...]:
    """The outcome classes a shell command belongs to (deterministic)."""
    return tuple(name for name, pattern in COMMAND_CLASS_PATTERNS if pattern.search(command))


def _command(record: AgentRecord) -> str | None:
    arguments = record.tool.arguments
    if not isinstance(arguments, dict):
        return None
    for key in ("command", "cmd", "script"):
        value = arguments.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _counters(records: list[AgentRecord]) -> dict[str, int]:
    counts: dict[str, int] = {
        "test_ok": 0,
        "test_total": 0,
        "build_ok": 0,
        "build_total": 0,
        "lint_ok": 0,
        "lint_total": 0,
        "reverted": 0,
        "interrupted": 0,
        "rejected": 0,
        "retries": 0,
    }
    previous: tuple[str, str] | None = None
    for record in records:
        command = _command(record)
        if command is not None:
            for class_name in command_classes(command):
                counts[f"{class_name}_total"] += 1
                if record.outcome.value == "ok":
                    counts[f"{class_name}_ok"] += 1
            if _REVERT_RE.search(command):
                counts["reverted"] += 1
        if record.security_event is not None and (
            record.security_event.type.value in _INTERRUPT_EVENTS
        ):
            counts["interrupted"] += 1
        if record.outcome.value == "denied" or (
            effective_authorization(record).source.value == "denied"
        ):
            counts["rejected"] += 1
        current = (record.tool.name, record.outcome.value)
        if (
            previous is not None
            and previous[0] == current[0]
            and previous[1] == "error"
            and current[1] == "ok"
        ):
            counts["retries"] += 1
        previous = current
    return counts


def _key_for(record: AgentRecord, by: str) -> str:
    if by == "session":
        return record.session_id
    if by == "project":
        return record.project or NO_KEY
    if by == "harness":
        return record.harness or NO_KEY
    if by == "model":
        from agentwatch.pricing import normalize_model

        return normalize_model(record.agent.model_version) or UNKNOWN_MODEL
    raise ValueError(f"unknown --by value {by!r}; expected one of {', '.join(BY_OPTIONS)}")


def _ratio(ok: int, total: int) -> Ratio:
    return Ratio(ok, total)


def build_outcomes(
    store: RecordStore,
    *,
    by: str = "project",
    since: str | None = None,
    now: datetime | None = None,
    repo: str | None = None,
) -> OutcomeReport:
    """Roll up deterministic outcome facts (no model, no network)."""
    if by not in BY_OPTIONS:
        raise ValueError(f"unknown --by value {by!r}; expected one of {', '.join(BY_OPTIONS)}")
    cutoff = since_cutoff(since, now=now) if since is not None else None
    records = [
        record for record in store.records() if cutoff is None or record.started_at >= cutoff
    ]
    sessions: dict[str, list[AgentRecord]] = {}
    for record in records:
        sessions.setdefault(record.session_id, []).append(record)

    retained = retained_changes(store, repo=repo, since=since, now=now)
    buckets: dict[str, dict[str, int]] = {}
    for session_id, items in sessions.items():
        counters = _counters(items)
        key = _key_for(items[0], by)
        bucket = buckets.setdefault(
            key, {"sessions": 0, "retained": 0, **{name: 0 for name in counters}}
        )
        bucket["sessions"] += 1
        for name, count in counters.items():
            bucket[name] += count
        if retained.known and session_id in retained.sessions:
            bucket["retained"] += 1

    rows = [
        OutcomeRow(
            key=key,
            sessions=bucket["sessions"],
            test_pass=_ratio(bucket["test_ok"], bucket["test_total"]),
            build_pass=_ratio(bucket["build_ok"], bucket["build_total"]),
            lint_pass=_ratio(bucket["lint_ok"], bucket["lint_total"]),
            retained=bucket.get("retained", 0),
            retained_known=retained.known,
            reverted=bucket["reverted"],
            interrupted=bucket["interrupted"],
            rejected=bucket["rejected"],
            retries_to_success=bucket["retries"],
        )
        for key, bucket in sorted(buckets.items())
    ]
    notes: list[str] = []
    if not records:
        notes.append("no records in the window")
    if not retained.known:
        notes.append("retained changes unknown: no git repository supplied")
    return OutcomeReport(by=by, since=since, rows=tuple(rows), notes=tuple(notes))


def render_outcomes(report: OutcomeReport) -> str:
    """Render an outcome rollup as short text (facts + derivation version)."""
    lines = [
        f"agentwatch outcomes --by {report.by} (derivation {report.derivation_version}, "
        f"rules {report.rules_version})"
    ]
    if not report.rows:
        lines.append("  no records in the window")
        return "\n".join(lines)
    lines.append("KEY\tSESSIONS\tTEST\tBUILD\tLINT\tRETAINED\tREJECTED\tRETRIES")
    for row in report.rows:
        retained = str(row.retained) if row.retained_known else "unknown"
        lines.append(
            f"{row.key}\t{row.sessions}\t{_ratio_text(row.test_pass)}\t"
            f"{_ratio_text(row.build_pass)}\t{_ratio_text(row.lint_pass)}\t{retained}\t"
            f"{row.rejected}\t{row.retries_to_success}"
        )
    for note in report.notes:
        lines.append(f"  note: {note}")
    return "\n".join(lines)


def _ratio_text(ratio: Ratio) -> str:
    return "unknown" if ratio.value is None else f"{ratio.numerator}/{ratio.denominator}"


# ---------------------------------------------------------------------------
# Retained change (join to PRV-1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetainedChanges:
    """Sessions whose recorded changes reached a later commit."""

    known: bool
    sessions: tuple[str, ...] = ()
    derivation_version: str = OUTCOME_DERIVATION_VERSION

    @property
    def count(self) -> int:
        return len(self.sessions)

    def to_dict(self) -> dict[str, object]:
        return {
            "known": self.known,
            "sessions": list(self.sessions),
            "count": self.count,
            "derivation_version": self.derivation_version,
        }


def _session_paths(records: Iterable[AgentRecord]) -> tuple[AgentRecord, tuple[str, ...]]:
    from agentwatch.classify import classify_record

    first = next(iter(records))
    paths: list[str] = []
    for record in records:
        for fact in classify_record(record):
            if (
                fact.category in _FILE_CATEGORIES
                and fact.target is not None
                and fact.target not in paths
            ):
                paths.append(fact.target)
    return first, tuple(paths)


def _git_log(repo: str) -> tuple[tuple[datetime, tuple[str, ...]], ...]:
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "-C", repo, "log", "--name-only", "--no-renames", "--format=__C__%cI"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    if result.returncode != 0:
        return ()
    commits: list[tuple[datetime, tuple[str, ...]]] = []
    current_time: datetime | None = None
    current_paths: list[str] = []
    for line in result.stdout.splitlines():
        if line.startswith("__C__"):
            if current_time is not None:
                commits.append((current_time, tuple(current_paths)))
            stamp = line[len("__C__") :].strip()
            try:
                parsed = datetime.fromisoformat(stamp)
            except ValueError:
                current_time = None
                current_paths = []
                continue
            current_time = (
                parsed.replace(tzinfo=timezone.utc)
                if parsed.tzinfo is None
                else parsed.astimezone(timezone.utc)
            )
            current_paths = []
        elif line.strip() and current_time is not None:
            current_paths.append(line.strip())
    if current_time is not None:
        commits.append((current_time, tuple(current_paths)))
    return tuple(commits)


def retained_changes(
    store: RecordStore,
    *,
    repo: str | None = None,
    since: str | None = None,
    now: datetime | None = None,
) -> RetainedChanges:
    """Which sessions' recorded changes reached a commit (deterministic, offline)."""
    if not repo or not os.path.isdir(repo):
        return RetainedChanges(known=False)
    commits = _git_log(repo)
    if not commits:
        return RetainedChanges(known=True)
    cutoff = since_cutoff(since, now=now) if since is not None else None
    sessions: dict[str, list[AgentRecord]] = {}
    for record in store.records():
        if cutoff is not None and record.started_at < cutoff:
            continue
        sessions.setdefault(record.session_id, []).append(record)
    retained: list[str] = []
    for session_id in sorted(sessions):
        first, paths = _session_paths(sessions[session_id])
        relative = {os.path.relpath(path, repo) if os.path.isabs(path) else path for path in paths}
        if not relative:
            continue
        for commit_time, commit_paths in commits:
            if commit_time < first.started_at:
                continue
            if relative & set(commit_paths):
                retained.append(session_id)
                break
    return RetainedChanges(known=True, sessions=tuple(retained))


__all__ = [
    "BY_OPTIONS",
    "COMMAND_CLASS_PATTERNS",
    "OUTCOME_DERIVATION_VERSION",
    "OUTCOME_RULES_VERSION",
    "OutcomeReport",
    "OutcomeRow",
    "Ratio",
    "RetainedChanges",
    "build_outcomes",
    "command_classes",
    "render_outcomes",
    "retained_changes",
]
