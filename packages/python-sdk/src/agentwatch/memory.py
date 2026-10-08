"""Agent memory-surface records (M28 DET-7, PRD 43 §DET-7).

Agent memory is a top attack surface and, before this, an audit gap (G9): a
record layer that cannot show what an agent read from, wrote to, or deleted from
memory is blind to "memory forensics". This module records memory reads, writes,
and deletes as ordinary records (tool name ``memory``), so they flow through the
chain, the views, and ``search``.

Privacy: the operation and key are **always** metadata; the memory *content* is
captured only when the privacy mode is not ``metadata-only`` **and** the
per-field ``capture_memory`` flag opts in (the same gate as tool args).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agentwatch.capabilities import (
    CAP_KIND_MEMORY,
    CHANGE_ADDED,
    CHANGE_REMOVED,
    COVERAGE_NONE,
    COVERAGE_PARTIAL,
    Capability,
)
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)
from agentwatch.redact import PrivacyMode, RedactionConfig
from agentwatch.store import RecordStore

MEMORY_TOOL = "memory"
MEMORY_OPERATIONS: tuple[str, ...] = ("read", "write", "delete")

# MEM-1: a memory store is a capability; a changed digest with no matching
# recorded write is "unattributed". Factual wording, never a verdict.
MEMORY_CHANGE_CHANGED = "content changed"
MEMORY_ROOT = "memory"

_PRIVACY_MAP = {
    PrivacyMode.METADATA_ONLY: RecordPrivacyMode.METADATA_ONLY,
    PrivacyMode.TRUNCATED: RecordPrivacyMode.TRUNCATED,
    PrivacyMode.HASHED: RecordPrivacyMode.HASHED,
    PrivacyMode.FULL: RecordPrivacyMode.FULL,
}


class MemoryError(ValueError):
    """Raised when a memory operation is unknown."""


def is_memory_record(record: AgentRecord) -> bool:
    """Whether a record describes a memory operation."""
    return record.tool.name == MEMORY_TOOL


def memory_record(
    session_id: str,
    operation: str,
    *,
    key: str | None = None,
    content: str | None = None,
    redaction: RedactionConfig | None = None,
    agent: AgentIdentity | None = None,
    now: datetime | None = None,
) -> AgentRecord:
    """Build a memory read/write/delete record (metadata always; content gated)."""
    if operation not in MEMORY_OPERATIONS:
        options = ", ".join(MEMORY_OPERATIONS)
        raise MemoryError(f"unknown memory operation {operation!r}; choose from {options}")
    arguments: dict[str, object] = {"operation": operation}
    if key is not None:
        arguments["key"] = key

    privacy = RecordPrivacyMode.METADATA_ONLY
    if content is not None and redaction is not None and redaction.capture_memory:
        redacted = redaction.apply(content, allowed=redaction.capture_memory)
        if redacted is not None:
            arguments["content"] = redacted
            privacy = _PRIVACY_MAP[redaction.mode]

    return AgentRecord(
        session_id=session_id,
        agent=agent or AgentIdentity(identity="agent"),
        tool=ToolCall(name=MEMORY_TOOL, arguments=arguments, privacy_mode=privacy),
        outcome=Outcome.OK,
        started_at=now or datetime.now(timezone.utc),
    )


@dataclass(frozen=True)
class MemoryReport:
    """Outcome of appending one memory record."""

    seq: int
    operation: str
    content_captured: bool


def record_memory(
    store: RecordStore,
    session_id: str,
    operation: str,
    *,
    key: str | None = None,
    content: str | None = None,
    redaction: RedactionConfig | None = None,
    now: datetime | None = None,
) -> MemoryReport:
    """Append a memory read/write/delete record; return its sequence."""
    record = memory_record(
        session_id, operation, key=key, content=content, redaction=redaction, now=now
    )
    entry = store.append(record)
    arguments = record.tool.arguments or {}
    return MemoryReport(
        seq=entry.seq,
        operation=operation,
        content_captured="content" in arguments,
    )


@dataclass(frozen=True)
class MemoryEvent:
    """One stored memory operation, for read-side views."""

    operation: str
    key: str | None
    content: str | None
    content_captured: bool
    at: datetime
    session_id: str
    seq: int = 0


def memory_events(store: RecordStore, *, session_id: str | None = None) -> list[MemoryEvent]:
    """Every stored memory operation, in store order (optionally one session)."""
    events: list[MemoryEvent] = []
    for entry in store.entries():
        record = entry.record
        if record is None or not is_memory_record(record):
            continue
        if session_id is not None and record.session_id != session_id:
            continue
        arguments = record.tool.arguments or {}
        content = arguments.get("content")
        events.append(
            MemoryEvent(
                operation=str(arguments.get("operation", "")),
                key=str(arguments["key"]) if isinstance(arguments.get("key"), str) else None,
                content=str(content) if content is not None else None,
                content_captured=content is not None,
                at=record.started_at,
                session_id=record.session_id,
                seq=entry.seq,
            )
        )
    return events


# ---------------------------------------------------------------------------
# Memory stores as capabilities (M30 MEM-1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemoryStore:
    """One persistent memory store: digest/size/last-changed, never content."""

    name: str
    scope: str
    digest: str
    size: int
    last_changed: datetime
    path: str

    def to_capability(self) -> Capability:
        """A MEM-1 memory store as an ordinary capability entry."""
        return Capability(
            kind=CAP_KIND_MEMORY,
            name=self.name,
            scope=self.scope,
            digest=self.digest,
            size=self.size,
            declared_version=None,
            origin=self.path,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "scope": self.scope,
            "digest": self.digest,
            "size": self.size,
            "last_changed": self.last_changed.isoformat(),
        }


def _digest_file(path: Path) -> tuple[str, int, datetime]:
    data = path.read_bytes()
    changed = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return hashlib.sha256(data).hexdigest(), len(data), changed


def discover_memory_stores(
    *, home: Path | None = None, project: Path | None = None
) -> tuple[MemoryStore, ...]:
    """Inventory Claude Code memory stores under ``~/.claude/memory`` / project."""
    resolved_home = (home or Path.home()).expanduser()
    resolved_project = (project or Path.cwd()).expanduser()
    roots = (
        (resolved_home / ".claude" / MEMORY_ROOT, "user"),
        (resolved_project / ".claude" / MEMORY_ROOT, "project"),
    )
    stores: list[MemoryStore] = []
    for root, scope in roots:
        if not root.is_dir():
            continue
        for entry in sorted(root.rglob("*.md")):
            if not entry.is_file():
                continue
            digest, size, changed = _digest_file(entry)
            stores.append(
                MemoryStore(
                    name=entry.stem,
                    scope=scope,
                    digest=digest,
                    size=size,
                    last_changed=changed,
                    path=str(entry),
                )
            )
    return tuple(stores)


def discover_memory_capabilities(
    *, home: Path | None = None, project: Path | None = None
) -> tuple[Capability, ...]:
    """The discovered memory stores, as capability entries."""
    return tuple(
        store.to_capability() for store in discover_memory_stores(home=home, project=project)
    )


def _key_matches(key: str, store: MemoryStore) -> bool:
    return key == store.path or key == store.name or key.rsplit("/", 1)[-1] == store.name


def attribute_memory_store(
    store: MemoryStore, records: Sequence[AgentRecord]
) -> str | None:
    """The latest session that recorded a write to this store, or ``None``."""
    for record in reversed(records):
        if not is_memory_record(record):
            continue
        arguments = record.tool.arguments or {}
        if arguments.get("operation") != "write":
            continue
        key = arguments.get("key")
        if isinstance(key, str) and _key_matches(key, store):
            return record.session_id
    return None


@dataclass(frozen=True)
class MemoryStoreChange:
    """A change to a memory store, with the writing session when known."""

    name: str
    scope: str
    change: str
    prev_digest: str | None
    digest: str | None
    last_changed: datetime | None
    attributed_session: str | None

    def is_unattributed(self) -> bool:
        """A change (not a removal) no recorded session declares writing."""
        return self.change != CHANGE_REMOVED and self.attributed_session is None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "scope": self.scope,
            "change": self.change,
            "prev_digest": self.prev_digest,
            "digest": self.digest,
            "last_changed": self.last_changed.isoformat() if self.last_changed else None,
            "attributed_session": self.attributed_session,
            "unattributed": self.is_unattributed(),
        }


def detect_memory_changes(
    before: Sequence[MemoryStore],
    after: Sequence[MemoryStore],
    records: Sequence[AgentRecord],
) -> list[MemoryStoreChange]:
    """Diff two memory-store snapshots, attributing each change to a writer."""
    before_map = {(store.scope, store.name): store for store in before}
    after_map = {(store.scope, store.name): store for store in after}
    changes: list[MemoryStoreChange] = []
    for key in sorted(set(before_map) | set(after_map)):
        prior = before_map.get(key)
        current = after_map.get(key)
        if prior is None and current is not None:
            change = CHANGE_ADDED
        elif current is None and prior is not None:
            change = CHANGE_REMOVED
        elif prior is not None and current is not None and prior.digest != current.digest:
            change = MEMORY_CHANGE_CHANGED
        else:
            continue
        attributed = attribute_memory_store(current, records) if current is not None else None
        changes.append(
            MemoryStoreChange(
                name=key[1],
                scope=key[0],
                change=change,
                prev_digest=prior.digest if prior else None,
                digest=current.digest if current else None,
                last_changed=current.last_changed if current else None,
                attributed_session=attributed,
            )
        )
    return changes


def render_memory_stores(stores: Sequence[MemoryStore]) -> str:
    if not stores:
        return "no memory stores"
    lines = ["NAME\tSCOPE\tSIZE\tLAST CHANGED\tDIGEST"]
    for store in stores:
        lines.append(
            f"{store.name}\t{store.scope}\t{store.size}\t"
            f"{store.last_changed.isoformat()}\t{store.digest}"
        )
    return "\n".join(lines)


@dataclass(frozen=True)
class MemoryExposure:
    """Per-harness memory-store exposure, declared honestly."""

    harness: str
    status: str
    note: str


MEMORY_EXPOSURE: tuple[MemoryExposure, ...] = (
    MemoryExposure(
        "claude-code",
        COVERAGE_PARTIAL,
        "directory-based discovery + writer attribution from recorded memory ops; "
        "auto-memory layout not pinned",
    ),
    MemoryExposure("cursor", COVERAGE_NONE, "no memory-store surface exposed"),
    MemoryExposure("codex-cli", COVERAGE_NONE, "no memory-store surface exposed"),
    MemoryExposure("gemini-cli", COVERAGE_NONE, "no memory-store surface exposed"),
)


def memory_exposure_matrix() -> tuple[MemoryExposure, ...]:
    """The published, CI-checked memory-exposure matrix (one row per harness)."""
    return MEMORY_EXPOSURE


__all__ = [
    "MEMORY_CHANGE_CHANGED",
    "MEMORY_EXPOSURE",
    "MEMORY_OPERATIONS",
    "MEMORY_TOOL",
    "MemoryError",
    "MemoryEvent",
    "MemoryExposure",
    "MemoryReport",
    "MemoryStore",
    "MemoryStoreChange",
    "attribute_memory_store",
    "detect_memory_changes",
    "discover_memory_capabilities",
    "discover_memory_stores",
    "is_memory_record",
    "memory_events",
    "memory_exposure_matrix",
    "memory_record",
    "record_memory",
    "render_memory_stores",
]
