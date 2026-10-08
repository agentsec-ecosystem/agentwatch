"""Code provenance & attribution (M30 PRV-1/PRV-2/PRV-3, PRD 53).

The record answers *what the agent did*; this module connects it to *the code it
produced*. Three parts, all **derived** views over the existing record schema and
git facts (no record-schema change):

* **PRV-3** (this section) — a content-free range+hash capture: per file-modifying
  call, the affected line range(s) and a keyed content hash, **never the content**.
  Under ``metadata-only`` the ranges+hashes still exist (they are metadata, not
  content); a harness that does not expose a range falls back to file-level
  ``heuristic`` attribution. ADR-0033.
* **PRV-1** — ``provenance <commit|range|PR|file>``: join a git fact to the
  records that produced it with a per-range confidence
  (``exact|heuristic|mixed|ambiguous|unknown``).
* **PRV-2** — Agent Trace export + git-ai notes cross-validation (``agent_trace``
  module), pinned revision + drift check.

Honesty rules (PRD 53): attribution is a claim with a confidence, never an
assumption. A commit with no recorded session says "no recorded agent activity"
— never "human". Hand edits after the agent are ``mixed``; two overlapping
sessions on one range are ``ambiguous``; gaps are flagged.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from agentwatch.query import since_cutoff
from agentwatch.records import AgentRecord
from agentwatch.store import RecordStore

# Bumped when the capture shape or the join semantics change (a consumer can
# branch on it). Published in docs/design/code-provenance.md.
RANGE_CAPTURE_VERSION = "prv3"
PROVENANCE_VERSION = "prv1"

EXACT = "exact"
HEURISTIC = "heuristic"
MIXED = "mixed"
AMBIGUOUS = "ambiguous"
UNKNOWN = "unknown"

CONFIDENCES: tuple[str, ...] = (EXACT, HEURISTIC, MIXED, AMBIGUOUS, UNKNOWN)

# A reserved key inside ``tool.arguments`` under which the content-free capture
# rides. It is *metadata* (ranges + keyed hashes), so it is legal under every
# privacy mode including ``metadata-only``; no record-schema change is needed.
AGENTWATCH_ATTRIBUTION_KEY = "agentwatch_attribution"

# Keys that would carry code content — the capture must never emit one. Used by
# the defensive ``is_content_free`` guard and the attack-pack test.
CONTENT_KEYS: frozenset[str] = frozenset(
    {
        "content",
        "new_content",
        "new_string",
        "old_string",
        "new_text",
        "text",
        "body",
        "diff",
        "patch",
        "hunk",
        "code",
    }
)

_HASH_PREFIX = "hmac-sha256:"
_FALLBACK_SALT = b"agentwatch.provenance.v1:"

_PATH_KEYS = ("file_path", "path", "notebook_path", "filename", "file")
_CONTENT_KEYS_ORDER = ("new_string", "new_content", "content", "new_text", "text", "old_string")
_START_KEYS = ("start_line", "line_start", "first_line")
_END_KEYS = ("end_line", "line_end", "last_line")
_LINE_RANGE_RE = re.compile(r"^\s*(\d+)\s*[-:]\s*(\d+)\s*$")


def _per_install_key() -> bytes | None:
    from agentwatch import flow

    return flow.hmac_key_or_none()


def _keyed_hash(text: str, *, key: bytes | None = None) -> str:
    """A stable, non-reversible handle for content.

    Keyed with the per-install HMAC key when available (the same keyed mechanism
    as identity/content-flow fingerprints) so identical content is correlatable
    within one installation but not recoverable — and never stored as content.
    """
    resolved = key if key is not None else _per_install_key()
    payload = text.encode("utf-8")
    if resolved:
        digest = hmac.new(resolved, payload, hashlib.sha256).hexdigest()
    else:
        digest = hashlib.sha256(_FALLBACK_SALT + payload).hexdigest()
    return _HASH_PREFIX + digest


@dataclass(frozen=True)
class LineRange:
    """An inclusive, 1-based line range affected by one file-modifying call."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 1 or self.end < self.start:
            raise ValueError(f"invalid line range {self.start}-{self.end}")

    def to_dict(self) -> dict[str, int]:
        return {"start": self.start, "end": self.end}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LineRange:
        return cls(int(data["start"]), int(data["end"]))


@dataclass(frozen=True)
class RangeCapture:
    """A content-free attribution fact for one file-modifying call (PRV-3).

    Carries the affected line range(s) and a keyed hash per captured content
    fragment; ``fallback`` is ``file-level`` when the harness exposed no range.
    Content is never a field here.
    """

    path: str | None
    ranges: tuple[LineRange, ...]
    hashes: tuple[str, ...]
    confidence: str
    fallback: str | None = None
    source_tool: str | None = None
    version: str = RANGE_CAPTURE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "path": self.path,
            "ranges": [line_range.to_dict() for line_range in self.ranges],
            "hashes": list(self.hashes),
            "confidence": self.confidence,
            "fallback": self.fallback,
            "source_tool": self.source_tool,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RangeCapture:
        ranges = data.get("ranges") or []
        hashes = data.get("hashes") or []
        return cls(
            path=data.get("path"),
            ranges=tuple(LineRange.from_dict(item) for item in ranges),
            hashes=tuple(str(item) for item in hashes),
            confidence=str(data.get("confidence", UNKNOWN)),
            fallback=data.get("fallback"),
            source_tool=data.get("source_tool"),
            version=str(data.get("version", RANGE_CAPTURE_VERSION)),
        )


def _path_from_arguments(arguments: Mapping[str, Any]) -> str | None:
    for key in _PATH_KEYS:
        value = arguments.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _content_fragments(arguments: Mapping[str, Any]) -> list[str]:
    fragments: list[str] = []
    for key in _CONTENT_KEYS_ORDER:
        value = arguments.get(key)
        if isinstance(value, str) and value:
            fragments.append(value)
    return fragments


def _int_argument(arguments: Mapping[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = arguments.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    return None


def _range_from_arguments(arguments: Mapping[str, Any]) -> tuple[LineRange, ...]:
    start = _int_argument(arguments, _START_KEYS)
    end = _int_argument(arguments, _END_KEYS)
    if start is not None and end is not None:
        return (LineRange(start, end),)
    raw = arguments.get("line_range")
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        return (LineRange(int(raw[0]), int(raw[1])),)
    if isinstance(raw, str):
        match = _LINE_RANGE_RE.match(raw)
        if match is not None:
            return (LineRange(int(match.group(1)), int(match.group(2))),)
    match = _LINE_RANGE_RE.match(str(arguments.get("lines", "")))
    if match is not None:
        return (LineRange(int(match.group(1)), int(match.group(2))),)
    return ()


def capture_ranges(
    arguments: Mapping[str, Any] | None,
    *,
    tool_name: str,
    privacy_mode: str | None = None,
    key: bytes | None = None,
) -> RangeCapture:
    """Capture the content-free range+hash facts for one file-modifying call.

    Works under **every** privacy mode: the output is metadata (ranges + keyed
    hashes), never content. An explicit range makes the capture ``exact``; when
    the harness did not expose a range the capture is file-level ``heuristic``.
    """
    args: Mapping[str, Any] = arguments or {}
    path = _path_from_arguments(args)
    ranges = _range_from_arguments(args)
    hashes = tuple(_keyed_hash(fragment, key=key) for fragment in _content_fragments(args))
    if ranges:
        confidence = EXACT
        fallback = None
        if not hashes:
            hashes = (_keyed_hash(f"{tool_name}:{path}", key=key),)
    else:
        confidence = HEURISTIC
        fallback = "file-level"
        if not hashes:
            hashes = (_keyed_hash(f"{tool_name}:{path}", key=key),)
    return RangeCapture(
        path=path,
        ranges=ranges,
        hashes=hashes,
        confidence=confidence,
        fallback=fallback,
        source_tool=tool_name,
    )


def to_attribution_arguments(capture: RangeCapture) -> dict[str, Any]:
    """Wrap a capture for storage in ``tool.arguments`` (content-free)."""
    return {AGENTWATCH_ATTRIBUTION_KEY: capture.to_dict()}


def range_facts_from_record(record: AgentRecord) -> RangeCapture | None:
    """Read the reserved content-free facts off a stored record, if present."""
    arguments = record.tool.arguments
    if not isinstance(arguments, Mapping):
        return None
    raw = arguments.get(AGENTWATCH_ATTRIBUTION_KEY)
    if not isinstance(raw, Mapping):
        return None
    return RangeCapture.from_dict(raw)


def is_content_free(payload: Any) -> bool:
    """Whether a payload (recursively) carries no code-content key.

    A defensive guard: the capture shape is content-free by construction, and
    this proves it for a serialized fact before it is stored or exported.
    """
    if isinstance(payload, Mapping):
        if CONTENT_KEYS & set(payload):
            return False
        return all(is_content_free(value) for value in payload.values())
    if isinstance(payload, (list, tuple)):
        return all(is_content_free(item) for item in payload)
    return True


def canonical_fact(payload: Mapping[str, Any]) -> str:
    """Deterministic serialization of a fact (stable across runs)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# ---------------------------------------------------------------------------
# PRV-1 — `provenance <commit|range|PR|file>`
# ---------------------------------------------------------------------------

NO_ACTIVITY = "no recorded agent activity"
_GIT_TIMEOUT_SECONDS = 2.0
_HEX_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
_PR_RE = re.compile(r"^(?:pr|#)?[:#/ ]?(\d+)$", re.IGNORECASE)
_FILE_LINES_RE = re.compile(r"^(?P<path>.+):(?P<start>\d+)(?:-(?P<end>\d+))?$")

_FILE_CATEGORIES = frozenset({"file:write", "file:edit", "file:delete"})


@dataclass(frozen=True)
class Target:
    """A parsed provenance target."""

    kind: str
    value: str
    lines: tuple[int, int] | None = None


def parse_target(target: str) -> Target:
    """Parse ``<commit|range|PR|file[:lines]>`` into a typed target.

    Unambiguous by shape: ``a..b`` is a range, 7–40 hex is a commit, ``PR<n>`` /
    ``#<n>`` is a pull request, everything else is a file (with an optional
    ``:start-end`` line suffix).
    """
    text = target.strip()
    if ".." in text:
        return Target("range", text)
    if _HEX_RE.match(text):
        return Target("commit", text)
    if text.lower().startswith("pr") or (text.startswith("#") and text[1:].isdigit()):
        match = _PR_RE.match(text)
        if match is not None:
            return Target("pr", match.group(1))
    lines_match = _FILE_LINES_RE.match(text)
    if lines_match is not None:
        start = int(lines_match.group("start"))
        end = int(lines_match.group("end") or start)
        return Target("file", lines_match.group("path"), (start, end))
    return Target("file", text)


@dataclass(frozen=True)
class CommitFacts:
    """The git facts for one commit (or an honest ``unavailable`` answer)."""

    requested: str
    revision: str | None
    available: bool = True
    paths: tuple[str, ...] = ()
    ranges: Mapping[str, tuple[LineRange, ...]] = field(default_factory=dict)
    committed_at: datetime | None = None
    message: str | None = None


@dataclass(frozen=True)
class ContributingSession:
    """A session that contributed to the queried code fact."""

    session_id: str
    agent: str
    harness: str | None = None
    model: str | None = None
    authorization: Mapping[str, int] = field(default_factory=dict)
    cost_usd: float | None = None
    cost_source: str = "unknown"
    anomalies: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    coverage: str = "unknown"
    evidence: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent": self.agent,
            "harness": self.harness,
            "model": self.model,
            "authorization": dict(self.authorization),
            "cost_usd": self.cost_usd,
            "cost_source": self.cost_source,
            "anomalies": list(self.anomalies),
            "capabilities": list(self.capabilities),
            "coverage": self.coverage,
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True)
class ProvenanceRange:
    """Attribution for one line range, with its confidence."""

    path: str
    confidence: str
    start: int | None = None
    end: int | None = None
    sessions: tuple[str, ...] = ()
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "sessions": list(self.sessions),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ProvenanceReport:
    """The contributing sessions and per-range attribution for one target."""

    target: str
    kind: str
    status: str
    revision: str | None = None
    project: str | None = None
    sessions: tuple[ContributingSession, ...] = ()
    ranges: tuple[ProvenanceRange, ...] = ()
    mixed: bool = False
    ambiguous: bool = False
    coverage_gaps: tuple[str, ...] = ()
    no_activity: bool = False
    read_only: bool = True
    notes: tuple[str, ...] = ()
    version: str = PROVENANCE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "target": self.target,
            "kind": self.kind,
            "revision": self.revision,
            "project": self.project,
            "status": self.status,
            "no_activity": self.no_activity,
            "read_only": self.read_only,
            "mixed": self.mixed,
            "ambiguous": self.ambiguous,
            "coverage_gaps": list(self.coverage_gaps),
            "sessions": [session.to_dict() for session in self.sessions],
            "ranges": [line_range.to_dict() for line_range in self.ranges],
            "notes": list(self.notes),
        }


class GitFacts:
    """A read-only git fact source (never writes to the repository).

    Degrades honestly: no ``git``, no repo, or a failure yields
    ``available=False`` (or an unresolved revision), never a guess.
    """

    def __init__(self, repo: str | None) -> None:
        self.repo = repo
        self.available = bool(repo) and os.path.isdir(str(repo))

    def _git(self, *args: str) -> subprocess.CompletedProcess[str] | None:
        if not self.available:
            return None
        try:
            return subprocess.run(  # noqa: S603 - fixed argv, no shell
                ["git", "-C", str(self.repo), *args],
                capture_output=True,
                text=True,
                timeout=_GIT_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None

    def commit_facts(self, revision: str) -> CommitFacts:
        resolved = self._git("rev-parse", "--verify", f"{revision}^{{commit}}")
        if resolved is None:
            return CommitFacts(requested=revision, revision=None, available=False)
        if resolved.returncode != 0:
            return CommitFacts(requested=revision, revision=None, available=self.available)
        full = resolved.stdout.strip()
        meta = self._git("show", "-s", "--format=%cI%x00%s", full)
        committed_at: datetime | None = None
        message: str | None = None
        if meta is not None and meta.returncode == 0:
            raw = meta.stdout.strip("\n")
            stamp, _, message = raw.partition("\x00")
            committed_at = _parse_git_time(stamp)
        ranges = self._changed_ranges(full)
        return CommitFacts(
            requested=revision,
            revision=full,
            available=True,
            paths=tuple(ranges),
            ranges=ranges,
            committed_at=committed_at,
            message=message or None,
        )

    def _changed_ranges(self, revision: str) -> dict[str, tuple[LineRange, ...]]:
        diff = self._git("show", "--unified=0", "--no-renames", "--format=", revision)
        if diff is None or diff.returncode != 0:
            return {}
        result: dict[str, tuple[LineRange, ...]] = {}
        current: str | None = None
        for line in diff.stdout.splitlines():
            if line.startswith("+++ b/"):
                current = line[len("+++ b/") :]
                if current == "/dev/null":
                    current = None
                else:
                    result.setdefault(current, ())
            elif line.startswith("@@") and current is not None:
                match = re.search(r"\+(\d+)(?:,(\d+))?", line)
                if match is None:
                    continue
                start = int(match.group(1))
                count = int(match.group(2) or "1")
                if count > 0:
                    result[current] = (
                        *result.get(current, ()),
                        LineRange(start, start + count - 1),
                    )
        return result

    def pr_commit(self, number: int) -> str | None:
        found = self._git("log", "--format=%H", f"--grep=(#{number})", "-n", "1")
        if found is None or found.returncode != 0 or not found.stdout.strip():
            return None
        return found.stdout.strip().splitlines()[0]


def _parse_git_time(text: str) -> datetime | None:
    value = text.strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize(path: str, base: str | None) -> str:
    expanded = os.path.expanduser(path)
    if not os.path.isabs(expanded) and base:
        expanded = os.path.join(base, expanded)
    return os.path.normpath(expanded)


def _record_commit(record: AgentRecord) -> str | None:
    environment = record.environment
    if not isinstance(environment, Mapping):
        return None
    vcs = environment.get("vcs")
    if isinstance(vcs, Mapping):
        commit = vcs.get("commit")
        if isinstance(commit, str) and commit:
            return commit
    return None


def _record_sessions(store: RecordStore) -> dict[str, list[AgentRecord]]:
    sessions: dict[str, list[AgentRecord]] = {}
    for record in store.records():
        sessions.setdefault(record.session_id, []).append(record)
    return sessions


def _file_hits(
    records: list[AgentRecord], normalized: str, base: str | None
) -> list[tuple[AgentRecord, RangeCapture | None]]:
    from agentwatch.classify import classify_record

    hits: list[tuple[AgentRecord, RangeCapture | None]] = []
    for record in records:
        capture = range_facts_from_record(record)
        if capture is not None and capture.path:
            candidate = _normalize(capture.path, record.project or base)
            if candidate == normalized:
                hits.append((record, capture))
                continue
        for fact in classify_record(record):
            if fact.category not in _FILE_CATEGORIES or fact.target is None:
                continue
            candidate = _normalize(fact.target, record.project or base)
            if candidate != normalized:
                continue
            hits.append((record, capture))
            break
    return hits


def _session_summary(session_id: str, records: list[AgentRecord]) -> ContributingSession:
    from agentwatch.records import effective_authorization

    authorization: dict[str, int] = {}
    anomalies: list[str] = []
    cost: float | None = None
    cost_source = "unknown"
    agent = "unknown"
    harness = records[0].harness if records else None
    model = records[0].agent.model_version if records else None
    for record in records:
        source = effective_authorization(record).source.value
        authorization[source] = authorization.get(source, 0) + 1
        if record.security_event is not None:
            anomalies.append(record.security_event.type.value)
        if record.outcome.value == "denied":
            anomalies.append("denied")
        if record.cost_usd is not None:
            cost = (cost or 0.0) + record.cost_usd
            cost_source = "exact"
        if record.agent.identity or record.agent.name:
            agent = record.agent.identity or record.agent.name or agent
    return ContributingSession(
        session_id=session_id,
        agent=agent,
        harness=harness,
        model=model,
        authorization=authorization,
        cost_usd=round(cost, 6) if cost is not None else None,
        cost_source=cost_source,
        anomalies=tuple(dict.fromkeys(anomalies)),
        capabilities=(),
        coverage="unknown",
        evidence={
            "session_id": session_id,
            "command": f"agentwatch export-session {session_id} --format aat",
        },
    )


def build_provenance(
    store: RecordStore,
    target: str,
    *,
    repo: str | None = None,
    project: str | None = None,
    git: GitFacts | None = None,
    window: str = "7d",
    now: datetime | None = None,
) -> ProvenanceReport:
    """Join a git/code fact to the recorded sessions that produced it."""
    parsed = parse_target(target)
    source = git if git is not None else GitFacts(repo)
    base = project or repo
    all_sessions = _record_sessions(store)
    if parsed.kind == "file":
        return _build_file(parsed, all_sessions, base, project)
    revision = parsed.value
    if parsed.kind == "pr":
        number = int(parsed.value)
        resolved: str | None = source.pr_commit(number) if source.available else None
        if resolved is None:
            return ProvenanceReport(
                target=target,
                kind="pr",
                status=f"no commit found for PR {parsed.value} in this repository",
                project=project,
                notes=("PR resolution is offline: it matches a merge/squash subject '(#N)'",),
            )
        revision = resolved
    facts = source.commit_facts(revision)
    return _build_commit(target, parsed, facts, all_sessions, base, project, window, now)


def _build_file(
    parsed: Target,
    sessions: dict[str, list[AgentRecord]],
    base: str | None,
    project: str | None,
) -> ProvenanceReport:
    normalized = _normalize(parsed.value, base)
    ranges: list[ProvenanceRange] = []
    contributors: dict[str, bool] = {}
    for session_id, records in sessions.items():
        hits = _file_hits(records, normalized, base)
        if not hits:
            continue
        has_range = False
        for _record, capture in hits:
            if capture is not None and capture.ranges:
                has_range = True
                for line_range in capture.ranges:
                    ranges.append(
                        ProvenanceRange(
                            path=normalized,
                            confidence=EXACT,
                            start=line_range.start,
                            end=line_range.end,
                            sessions=(session_id,),
                        )
                    )
            else:
                ranges.append(
                    ProvenanceRange(
                        path=normalized,
                        confidence=HEURISTIC,
                        sessions=(session_id,),
                        reason="tool did not expose a line range",
                    )
                )
        contributors[session_id] = has_range
    if parsed.lines is not None:
        ranges.append(
            ProvenanceRange(
                path=normalized,
                confidence=EXACT if contributors else UNKNOWN,
                start=parsed.lines[0],
                end=parsed.lines[1],
                sessions=tuple(contributors),
                reason=None if contributors else "no recorded session covers the range",
            )
        )
    contributing = tuple(
        _session_summary(session_id, sessions[session_id]) for session_id in contributors
    )
    gaps = tuple(
        sorted(session_id for session_id, has_range in contributors.items() if not has_range)
    )
    no_activity = not contributors
    return ProvenanceReport(
        target=parsed.value,
        kind="file",
        status=NO_ACTIVITY if no_activity else "attributed",
        project=project,
        sessions=contributing,
        ranges=tuple(ranges),
        coverage_gaps=gaps,
        no_activity=no_activity,
        notes=_CAPABILITY_NOTE,
    )


_CAPABILITY_NOTE = ("loaded capabilities are not recorded in this build (M30 CAP-1)",)


def _build_commit(
    target: str,
    parsed: Target,
    facts: CommitFacts,
    sessions: dict[str, list[AgentRecord]],
    base: str | None,
    project: str | None,
    window: str,
    now: datetime | None,
) -> ProvenanceReport:
    if not facts.available:
        return ProvenanceReport(
            target=target,
            kind=parsed.kind,
            status="git repository unavailable; cannot resolve a commit",
            project=project,
            notes=_CAPABILITY_NOTE,
        )
    if facts.revision is None:
        return ProvenanceReport(
            target=target,
            kind=parsed.kind,
            status=f"unknown revision {facts.requested} in this repository",
            project=project,
            notes=_CAPABILITY_NOTE,
        )
    cutoff = (
        since_cutoff(window, now=facts.committed_at or now)
        if (facts.committed_at is not None or now is not None)
        else None
    )
    contributors: dict[str, bool] = {}
    ranges: list[ProvenanceRange] = []
    for path, hunks in facts.ranges.items():
        normalized = _normalize(path, base)
        path_sessions: dict[str, list[RangeCapture]] = {}
        heuristic_sessions: list[str] = []
        direct_sessions: list[str] = []
        for session_id, records in sessions.items():
            hits = _file_hits(records, normalized, base)
            if not hits:
                continue
            in_window = True
            for record, _capture in hits:
                if facts.committed_at is not None and record.started_at > facts.committed_at:
                    in_window = False
                if cutoff is not None and record.started_at < cutoff:
                    in_window = False
                commit = _record_commit(record)
                if commit is not None and facts.revision.startswith(commit):
                    direct_sessions.append(session_id)
            if not in_window and session_id not in direct_sessions:
                continue
            captures = [capture for _record, capture in hits if capture is not None]
            if any(capture.ranges for capture in captures):
                path_sessions[session_id] = [c for c in captures if c.ranges]
            else:
                heuristic_sessions.append(session_id)
            contributors.setdefault(session_id, False)
        contributors.update({session_id: True for session_id in path_sessions})
        for hunk in hunks:
            ranges.append(_attribute_hunk(normalized, hunk, path_sessions, heuristic_sessions))
        if not path_sessions and not heuristic_sessions:
            for hunk in hunks:
                ranges.append(
                    ProvenanceRange(
                        path=normalized,
                        confidence=UNKNOWN,
                        start=hunk.start,
                        end=hunk.end,
                        reason="no recorded session covers the range",
                    )
                )
    contributing = tuple(
        _session_summary(session_id, sessions[session_id]) for session_id in contributors
    )
    mixed = any(line_range.confidence == MIXED for line_range in ranges)
    ambiguous = any(line_range.confidence == AMBIGUOUS for line_range in ranges)
    gaps = tuple(
        sorted(session_id for session_id, has_range in contributors.items() if not has_range)
    )
    no_activity = not contributing
    return ProvenanceReport(
        target=target,
        kind=parsed.kind,
        status=NO_ACTIVITY if no_activity else "attributed",
        revision=facts.revision,
        project=project,
        sessions=contributing,
        ranges=tuple(ranges),
        mixed=mixed,
        ambiguous=ambiguous,
        coverage_gaps=gaps,
        no_activity=no_activity,
        notes=_CAPABILITY_NOTE,
    )


def _attribute_hunk(
    path: str,
    hunk: LineRange,
    path_sessions: Mapping[str, list[RangeCapture]],
    heuristic_sessions: list[str],
) -> ProvenanceRange:
    covering: list[str] = []
    covered_lines: set[int] = set()
    for session_id, captures in path_sessions.items():
        for capture in captures:
            for line_range in capture.ranges:
                overlap_start = max(line_range.start, hunk.start)
                overlap_end = min(line_range.end, hunk.end)
                if overlap_start <= overlap_end:
                    covering.append(session_id)
                    covered_lines.update(range(overlap_start, overlap_end + 1))
    unique = tuple(dict.fromkeys(covering))
    if not unique:
        if heuristic_sessions:
            return ProvenanceRange(
                path=path,
                confidence=HEURISTIC,
                start=hunk.start,
                end=hunk.end,
                sessions=tuple(dict.fromkeys(heuristic_sessions)),
                reason="file-level attribution: tool did not expose a line range",
            )
        return ProvenanceRange(
            path=path,
            confidence=UNKNOWN,
            start=hunk.start,
            end=hunk.end,
            reason="no recorded session covers the range",
        )
    if len(unique) > 1:
        return ProvenanceRange(
            path=path,
            confidence=AMBIGUOUS,
            start=hunk.start,
            end=hunk.end,
            sessions=unique,
            reason="two or more sessions edited the same range",
        )
    if len(covered_lines) < (hunk.end - hunk.start + 1):
        return ProvenanceRange(
            path=path,
            confidence=MIXED,
            start=hunk.start,
            end=hunk.end,
            sessions=unique,
            reason="part of the range has no recorded agent activity",
        )
    return ProvenanceRange(
        path=path,
        confidence=EXACT,
        start=hunk.start,
        end=hunk.end,
        sessions=unique,
    )


def render_provenance(report: ProvenanceReport) -> str:
    """Render a provenance report as short text."""
    lines = [f"agentwatch provenance {report.target} ({report.kind})"]
    lines.append(f"  status: {report.status}")
    if report.revision:
        lines.append(f"  revision: {report.revision}")
    if report.coverage_gaps:
        lines.append(f"  coverage gaps: {', '.join(report.coverage_gaps)}")
    for session in report.sessions:
        lines.append(
            f"  session {session.session_id} harness={session.harness or 'unknown'} "
            f"model={session.model or 'unknown'} coverage={session.coverage}"
        )
    for line_range in report.ranges:
        span = f"{line_range.start}-{line_range.end}" if line_range.start is not None else "(file)"
        lines.append(f"  {line_range.path}:{span} {line_range.confidence}")
    for note in report.notes:
        lines.append(f"  note: {note}")
    return "\n".join(lines)


__all__ = [
    "AGENTWATCH_ATTRIBUTION_KEY",
    "AMBIGUOUS",
    "CONFIDENCES",
    "CONTENT_KEYS",
    "EXACT",
    "HEURISTIC",
    "MIXED",
    "NO_ACTIVITY",
    "PROVENANCE_VERSION",
    "RANGE_CAPTURE_VERSION",
    "UNKNOWN",
    "CommitFacts",
    "ContributingSession",
    "GitFacts",
    "LineRange",
    "ProvenanceRange",
    "ProvenanceReport",
    "RangeCapture",
    "Target",
    "build_provenance",
    "canonical_fact",
    "capture_ranges",
    "is_content_free",
    "parse_target",
    "range_facts_from_record",
    "render_provenance",
    "to_attribution_arguments",
]
