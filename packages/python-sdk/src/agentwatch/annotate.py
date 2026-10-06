"""Operator annotations in the chain (M15 S20, #236).

An investigation produces a conclusion; without a place to put it the store holds
machine evidence and no human judgment. ``annotate`` appends a metadata-only
``operator-note`` record using the same marker-record convention as
``session-purge``: append-only (corrections are new records), metadata first, and
free text redacted + length-capped before it is stored.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)
from agentwatch.secrets import redact_secrets
from agentwatch.store import MARKER_PRODUCER, RecordStore

OPERATOR_NOTE_TOOL = "operator-note"
PURGE_TOOL = "session-purge"

# Cap the stored note so untrusted free text cannot bloat the chain or a view.
NOTE_MAX_LENGTH = 4096
TAG_MAX_LENGTH = 64
INCIDENT_TAG_MAX_LENGTH = 128
INCIDENT_TAG_MAX_COUNT = 32


class AnnotateError(ValueError):
    """Raised when a note cannot be stored (empty, or no such session)."""


@dataclass(frozen=True)
class AnnotateReport:
    """Outcome of appending one operator note."""

    session_id: str
    seq: int
    tag: str | None
    session_purged: bool
    masked_kinds: tuple[str, ...]


def _has_purge_marker(records: list[AgentRecord], session_id: str) -> bool:
    return any(
        record.session_id == session_id and record.tool.name == PURGE_TOOL for record in records
    )


def _has_live_records(records: list[AgentRecord], session_id: str) -> bool:
    return any(
        record.session_id == session_id and record.tool.name not in (OPERATOR_NOTE_TOOL, PURGE_TOOL)
        for record in records
    )


def annotate_session(
    store: RecordStore,
    session_id: str,
    note: str,
    *,
    tag: str | None = None,
    incident_tags: Sequence[str] | None = None,
    now: datetime | None = None,
) -> AnnotateReport:
    """Append a metadata-only ``operator-note`` record for ``session_id``.

    The note is stripped, length-capped, and run through the redactor before it is
    stored (a secret in a note is masked, never persisted). An empty note is
    rejected. A note on a session whose records were purged is allowed and tagged
    with an explicit ``session_purged`` context; an unknown session is rejected.
    ``incident_tags`` (COR-2) are metadata-only registry tags, each scrubbed and
    capped.
    """
    if not isinstance(note, str) or not note.strip():
        raise AnnotateError("note must not be empty")
    text = note.strip()
    if len(text) > NOTE_MAX_LENGTH:
        text = text[:NOTE_MAX_LENGTH]

    clean_tag: str | None = None
    if tag is not None:
        candidate = tag.strip()
        if not candidate:
            raise AnnotateError("tag must not be empty when provided")
        clean_tag = candidate[:TAG_MAX_LENGTH]

    clean_incident_tags: list[str] = []
    if incident_tags is not None:
        if len(incident_tags) > INCIDENT_TAG_MAX_COUNT:
            raise AnnotateError(f"at most {INCIDENT_TAG_MAX_COUNT} incident tags")
        for item in incident_tags:
            candidate = item.strip() if isinstance(item, str) else ""
            if not candidate:
                raise AnnotateError("incident tag must not be empty")
            clean_incident_tags.append(candidate[:INCIDENT_TAG_MAX_LENGTH])

    records = store.records()
    live = _has_live_records(records, session_id)
    purged = _has_purge_marker(records, session_id)
    if not live and not purged:
        raise AnnotateError(f"no records for session {session_id}")

    masked, kinds = redact_secrets(text)
    all_kinds = list(kinds)
    arguments: dict[str, object] = {"note": masked}
    if clean_tag is not None:
        arguments["tag"] = clean_tag
    if clean_incident_tags:
        scrubbed_tags: list[str] = []
        for item in clean_incident_tags:
            masked_tag, tag_kinds = redact_secrets(item)
            scrubbed_tags.append(masked_tag)
            all_kinds.extend(tag_kinds)
        arguments["incident_tags"] = scrubbed_tags
    session_purged = purged and not live
    if session_purged:
        arguments["session_purged"] = True
        arguments["context"] = "session purged"

    record = AgentRecord(
        session_id=session_id,
        agent=AgentIdentity(identity="agentwatch"),
        tool=ToolCall(
            name=OPERATOR_NOTE_TOOL,
            arguments=arguments,
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
        outcome=Outcome.OK,
        started_at=now or datetime.now(timezone.utc),
        producer=MARKER_PRODUCER,
    )
    entry = store.append(record)
    return AnnotateReport(
        session_id=session_id,
        seq=entry.seq,
        tag=clean_tag,
        session_purged=session_purged,
        masked_kinds=tuple(all_kinds),
    )


@dataclass(frozen=True)
class OperatorNote:
    """One stored annotation, for read-side views and the S1 findings section."""

    session_id: str
    note: str
    tag: str | None
    session_purged: bool
    at: datetime
    seq: int


def operator_notes(store: RecordStore, *, session_id: str | None = None) -> list[OperatorNote]:
    """Every stored operator note, in store order (optionally one session)."""
    notes: list[OperatorNote] = []
    for entry in store.entries():
        record = entry.record
        if record is None or record.tool.name != OPERATOR_NOTE_TOOL:
            continue
        if session_id is not None and record.session_id != session_id:
            continue
        arguments = record.tool.arguments or {}
        note = arguments.get("note")
        tag = arguments.get("tag")
        notes.append(
            OperatorNote(
                session_id=record.session_id,
                note=str(note) if note is not None else "",
                tag=str(tag) if isinstance(tag, str) else None,
                session_purged=bool(arguments.get("session_purged", False)),
                at=record.started_at,
                seq=entry.seq,
            )
        )
    return notes


def tagged_sessions(store: RecordStore, tag: str) -> set[str]:
    """Session ids that carry an operator note with ``tag``."""
    return {note.session_id for note in operator_notes(store) if note.tag == tag}
