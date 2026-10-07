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

from dataclasses import dataclass
from datetime import datetime, timezone

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


__all__ = [
    "MEMORY_OPERATIONS",
    "MEMORY_TOOL",
    "MemoryError",
    "MemoryEvent",
    "MemoryReport",
    "is_memory_record",
    "memory_events",
    "memory_record",
    "record_memory",
]
