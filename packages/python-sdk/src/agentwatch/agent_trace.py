"""Agent Trace export + git-ai notes cross-validation (M30 PRV-2, PRD 53).

Agent Trace is an open, storage-agnostic spec (RFC v0.1, Jan 2026) adopted by
Cursor, Cognition, Jules, Amp, OpenCode, Cline and git-ai. agentwatch emits
spec-shaped records from its evidence-grade store — **ranges / hashes / ids
only, never code content** — and cross-validates against existing Agent Trace /
git-ai notes rather than duplicating them.

Two honesty rules, mirroring the AAT export (ADR-0016):

* **lossless-or-explicit** — a field we cannot populate is listed in ``unmapped``
  with a reason; a value is never invented.
* **cite the revision** — we pin ``AGENT_TRACE_SPEC_REVISION`` and never claim
  conformance to "the standard"; a drift check surfaces a revision move.
* **write only by explicit command** — export is to a file/stdout by default;
  writing into a repository (git notes) requires the separate explicit command.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentwatch.provenance import (
    LineRange,
    RangeCapture,
    is_content_free,
    range_facts_from_record,
)
from agentwatch.records import AgentRecord

# Pinned Agent Trace revision. A drift check (scripts/agent_trace_drift_check.py)
# compares this against schema/agent-trace/upstream-revision.json.
AGENT_TRACE_SPEC_REVISION = "agent-trace-rfc-0.1"
AGENT_TRACE_EXPORT_SCHEMA = "agentwatch-agent-trace-export/1"
AGENT_TRACE_NOTES_REF = "agentwatch/agent-trace"

# Agent Trace concept -> agentwatch source. Published in docs/design/code-provenance.md.
AGENT_TRACE_MAPPING: dict[str, str] = {
    "conversation": "session_id (conversation reference)",
    "contributor.type": "agent (AI) — never 'human'",
    "contributor.model": "agent.model_version",
    "contributor.harness": "record.harness",
    "vcs.revision": "session-start environment.vcs.commit",
    "files[].path": "classified file-modification target",
    "files[].ranges": "PRV-3 content-free line ranges",
    "files[].content_hash": "PRV-3 keyed content hash",
}

# Agent Trace fields we map; a pinned revision that drops one is drift.
AGENT_TRACE_SPEC_FIELDS: tuple[str, ...] = (
    "conversation",
    "contributor",
    "vcs",
    "files",
)

# Fields agentwatch cannot populate: surfaced, never invented.
AGENT_TRACE_UNMAPPED: dict[str, str] = {
    "response_hash": "no pre-redaction response fingerprint captured on the record",
    "response_size": "pre-redaction response byte size not captured on the record",
}


@dataclass(frozen=True)
class AgentTraceFile:
    """One file entry in a trace record (content-free)."""

    path: str
    ranges: tuple[LineRange, ...] = ()
    content_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "ranges": [line_range.to_dict() for line_range in self.ranges],
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AgentTraceFile:
        ranges = data.get("ranges") or []
        return cls(
            path=str(data["path"]),
            ranges=tuple(LineRange.from_dict(item) for item in ranges),
            content_hash=data.get("content_hash"),
        )


@dataclass(frozen=True)
class AgentTraceRecord:
    """One Agent-Trace-shaped record (a single contributor action)."""

    revision: str | None
    conversation_id: str
    contributor_type: str
    contributor_model: str | None
    contributor_harness: str | None
    files: tuple[AgentTraceFile, ...] = ()
    unmapped: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_version": AGENT_TRACE_SPEC_REVISION,
            "conversation": {"id": self.conversation_id},
            "contributor": {
                "type": self.contributor_type,
                "model": self.contributor_model,
                "harness": self.contributor_harness,
            },
            "vcs": {"revision": self.revision},
            "files": [entry.to_dict() for entry in self.files],
            "unmapped": dict(self.unmapped),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AgentTraceRecord:
        contributor = data.get("contributor") or {}
        vcs = data.get("vcs") or {}
        conversation = data.get("conversation") or {}
        if not isinstance(contributor, Mapping) or not isinstance(vcs, Mapping):
            raise ValueError("agent-trace: contributor/vcs must be objects")
        if not isinstance(conversation, Mapping):
            raise ValueError("agent-trace: conversation must be an object")
        files = data.get("files") or []
        unmapped = data.get("unmapped") or {}
        return cls(
            revision=vcs.get("revision"),
            conversation_id=str(conversation.get("id", "")),
            contributor_type=str(contributor.get("type", "unknown")),
            contributor_model=contributor.get("model"),
            contributor_harness=contributor.get("harness"),
            files=tuple(AgentTraceFile.from_dict(item) for item in files),
            unmapped={str(k): str(v) for k, v in unmapped.items()},
        )


def _revision(record: AgentRecord) -> str | None:
    environment = record.environment
    if not isinstance(environment, Mapping):
        return None
    vcs = environment.get("vcs")
    if isinstance(vcs, Mapping):
        commit = vcs.get("commit")
        if isinstance(commit, str) and commit:
            return commit
    return None


def agent_trace_record(record: AgentRecord) -> AgentTraceRecord:
    """Map one agentwatch record to an Agent-Trace-shaped record (no content)."""
    capture: RangeCapture | None = range_facts_from_record(record)
    files: tuple[AgentTraceFile, ...] = ()
    unmapped = dict(AGENT_TRACE_UNMAPPED)
    if capture is not None and capture.path and capture.ranges:
        files = (
            AgentTraceFile(
                path=capture.path,
                ranges=capture.ranges,
                content_hash=capture.hashes[0] if capture.hashes else None,
            ),
        )
    else:
        unmapped["ranges"] = "tool did not expose a line range (file-level heuristic)"
    return AgentTraceRecord(
        revision=_revision(record),
        conversation_id=record.session_id,
        contributor_type="ai",
        contributor_model=record.agent.model_version,
        contributor_harness=record.harness,
        files=files,
        unmapped=unmapped,
    )


def export_agent_trace(export: Any, *, privacy_mode: str) -> dict[str, Any]:
    """Build the Agent Trace bundle for a session export."""
    records = [
        agent_trace_record(AgentRecord.from_dict(row["record"])).to_dict()
        for row in export.rows
    ]
    return {
        "schema": AGENT_TRACE_EXPORT_SCHEMA,
        "trace_version": AGENT_TRACE_SPEC_REVISION,
        "session_id": export.session_id,
        "privacy_mode": privacy_mode,
        "records": records,
        "unmapped": dict(AGENT_TRACE_UNMAPPED),
    }


def to_agent_trace_json(bundle: Mapping[str, Any]) -> str:
    """Render a bundle as deterministic, pretty JSON."""
    return json.dumps(bundle, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def write_agent_trace(bundle: Mapping[str, Any], path: Path) -> None:
    """Write an Agent Trace bundle to ``path`` atomically (explicit, user-called)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(to_agent_trace_json(bundle), encoding="utf-8")
    tmp.replace(path)


def read_agent_trace(payload: Any) -> tuple[AgentTraceRecord, ...]:
    """Read an Agent Trace bundle or record list into records (never raises on shape)."""
    records: Any
    if isinstance(payload, Mapping):
        records = payload.get("records", [])
    elif isinstance(payload, list):
        records = payload
    else:
        return ()
    if not isinstance(records, list):
        return ()
    parsed: list[AgentTraceRecord] = []
    for item in records:
        if not isinstance(item, Mapping):
            continue
        try:
            parsed.append(AgentTraceRecord.from_dict(item))
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(parsed)


def verify_agent_trace(bundle: Any) -> bool:
    """Whether a bundle is the pinned revision, well-formed, and content-free."""
    if not isinstance(bundle, Mapping):
        return False
    if bundle.get("trace_version") != AGENT_TRACE_SPEC_REVISION:
        return False
    records = bundle.get("records")
    if not isinstance(records, list):
        return False
    for record in records:
        if not isinstance(record, Mapping):
            return False
        if not isinstance(record.get("contributor"), Mapping):
            return False
        if not isinstance(record.get("vcs"), Mapping):
            return False
    return is_content_free(records)


@dataclass(frozen=True)
class AgentTraceDriftReport:
    """The result of comparing our pinned revision against an upstream descriptor."""

    pinned: str
    upstream: str
    missing: tuple[str, ...] = ()
    extra: tuple[str, ...] = ()

    @property
    def drifted(self) -> bool:
        return self.pinned != self.upstream or bool(self.missing)

    def to_dict(self) -> dict[str, object]:
        return {
            "pinned_revision": self.pinned,
            "upstream_revision": self.upstream,
            "missing": list(self.missing),
            "extra": list(self.extra),
            "drifted": self.drifted,
        }


def check_agent_trace_drift(upstream: Any) -> AgentTraceDriftReport:
    """Compare the pinned Agent Trace revision against an upstream descriptor.

    A revision bump, or an upstream field we map that disappeared, is drift; a
    brand-new upstream field is informational only.
    """
    revision = "<unknown>"
    known: set[str] = set()
    has_fields = False
    if isinstance(upstream, Mapping):
        raw = upstream.get("revision")
        if isinstance(raw, str):
            revision = raw
        fields = upstream.get("fields")
        if isinstance(fields, (list, tuple)):
            has_fields = True
            known = {str(field) for field in fields}
    missing = (
        tuple(sorted(field for field in AGENT_TRACE_SPEC_FIELDS if field not in known))
        if has_fields
        else ()
    )
    extra = tuple(sorted(field for field in known if field not in AGENT_TRACE_SPEC_FIELDS))
    return AgentTraceDriftReport(
        pinned=AGENT_TRACE_SPEC_REVISION, upstream=revision, missing=missing, extra=extra
    )


@dataclass(frozen=True)
class CrossValidationEntry:
    """One (revision, path) key and how agentwatch and the notes compare."""

    revision: str | None
    path: str | None
    verdict: str  # agree | disagree | agentwatch-only | notes-only
    agentwatch_session: str | None = None
    notes_session: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "path": self.path,
            "verdict": self.verdict,
            "agentwatch_session": self.agentwatch_session,
            "notes_session": self.notes_session,
        }


@dataclass(frozen=True)
class CrossValidationReport:
    """How agentwatch's attribution compares to existing Agent Trace / git-ai notes."""

    agree: int = 0
    disagree: int = 0
    agentwatch_only: int = 0
    notes_only: int = 0
    entries: tuple[CrossValidationEntry, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "agree": self.agree,
            "disagree": self.disagree,
            "agentwatch_only": self.agentwatch_only,
            "notes_only": self.notes_only,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def _keys(
    records: Sequence[AgentTraceRecord],
) -> dict[tuple[str | None, str | None], AgentTraceRecord]:
    keys: dict[tuple[str | None, str | None], AgentTraceRecord] = {}
    for record in records:
        if record.files:
            for entry in record.files:
                keys[(record.revision, entry.path)] = record
        else:
            keys[(record.revision, None)] = record
    return keys


def cross_validate(
    ours: Sequence[AgentTraceRecord], theirs: Sequence[AgentTraceRecord]
) -> CrossValidationReport:
    """Classify per (revision, path) how agentwatch and the notes compare."""
    our_keys = _keys(ours)
    their_keys = _keys(theirs)
    entries: list[CrossValidationEntry] = []
    agree = disagree = agentwatch_only = notes_only = 0
    for key in sorted(
        set(our_keys) | set(their_keys), key=lambda item: (str(item[0]), str(item[1]))
    ):
        revision, path = key
        in_ours = key in our_keys
        in_theirs = key in their_keys
        if in_ours and in_theirs:
            our_record = our_keys[key]
            their_record = their_keys[key]
            if _conflicts(our_record, their_record, path):
                disagree += 1
                entries.append(
                    CrossValidationEntry(
                        revision,
                        path,
                        "disagree",
                        our_record.conversation_id,
                        their_record.conversation_id,
                    )
                )
            else:
                agree += 1
                entries.append(CrossValidationEntry(revision, path, "agree"))
        elif in_ours:
            agentwatch_only += 1
            entries.append(
                CrossValidationEntry(
                    revision, path, "agentwatch-only", our_keys[key].conversation_id, None
                )
            )
        else:
            notes_only += 1
            entries.append(
                CrossValidationEntry(
                    revision, path, "notes-only", None, their_keys[key].conversation_id
                )
            )
    return CrossValidationReport(
        agree=agree,
        disagree=disagree,
        agentwatch_only=agentwatch_only,
        notes_only=notes_only,
        entries=tuple(entries),
    )


def _ranges_for(record: AgentTraceRecord, path: str | None) -> set[int]:
    lines: set[int] = set()
    for entry in record.files:
        if path is not None and entry.path != path:
            continue
        for line_range in entry.ranges:
            lines.update(range(line_range.start, line_range.end + 1))
    return lines


def _conflicts(ours: AgentTraceRecord, theirs: AgentTraceRecord, path: str | None) -> bool:
    our_lines = _ranges_for(ours, path)
    their_lines = _ranges_for(theirs, path)
    return bool(our_lines and their_lines and not (our_lines & their_lines))


def write_agent_trace_notes(
    repo: str, records: Sequence[AgentTraceRecord | Mapping[str, Any]]
) -> int:
    """Write Agent Trace notes into a repository (explicit, consented command).

    Returns the number of revisions written. Never called by default: the export
    path only ever writes to a file or stdout.
    """
    by_revision: dict[str, AgentTraceRecord] = {}
    for item in records:
        record = item if isinstance(item, AgentTraceRecord) else AgentTraceRecord.from_dict(item)
        if record.revision:
            by_revision[record.revision] = record
    written = 0
    for revision, record in by_revision.items():
        payload = json.dumps(record.to_dict(), sort_keys=True)
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [
                "git",
                "-C",
                repo,
                "notes",
                f"--ref={AGENT_TRACE_NOTES_REF}",
                "add",
                "-f",
                "-m",
                payload,
                revision,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            written += 1
    return written


def read_agent_trace_notes(repo: str, revision: str | None = None) -> tuple[AgentTraceRecord, ...]:
    """Read Agent Trace notes from a repository (read-only)."""
    objects: list[str] = []
    if revision:
        objects = [revision]
    else:
        listed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "-C", repo, "notes", f"--ref={AGENT_TRACE_NOTES_REF}", "list"],
            capture_output=True,
            text=True,
            check=False,
        )
        if listed.returncode != 0:
            return ()
        for line in listed.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                objects.append(parts[1])
    parsed: list[AgentTraceRecord] = []
    for obj in objects:
        shown = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "-C", repo, "notes", f"--ref={AGENT_TRACE_NOTES_REF}", "show", obj],
            capture_output=True,
            text=True,
            check=False,
        )
        if shown.returncode != 0:
            continue
        for line in shown.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                parsed.append(AgentTraceRecord.from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
    return tuple(parsed)


__all__ = [
    "AGENT_TRACE_EXPORT_SCHEMA",
    "AGENT_TRACE_MAPPING",
    "AGENT_TRACE_NOTES_REF",
    "AGENT_TRACE_SPEC_FIELDS",
    "AGENT_TRACE_SPEC_REVISION",
    "AGENT_TRACE_UNMAPPED",
    "AgentTraceDriftReport",
    "AgentTraceFile",
    "AgentTraceRecord",
    "CrossValidationEntry",
    "CrossValidationReport",
    "agent_trace_record",
    "check_agent_trace_drift",
    "cross_validate",
    "export_agent_trace",
    "read_agent_trace",
    "read_agent_trace_notes",
    "to_agent_trace_json",
    "verify_agent_trace",
    "write_agent_trace",
    "write_agent_trace_notes",
]
