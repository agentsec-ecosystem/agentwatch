"""Seal and archive old chain segments (M16 S28, #243).

NFR-3 promises bounded storage growth and R11 delivers retention — but retention
*tombstones*, which by design keeps every line so the chain still verifies: the
file never shrinks. ``agentwatch archive --before DATE`` moves the oldest prefix
of the chain into a **sealed segment file** that is itself a valid store, leaves a
single **anchor record** in the live store (segment id, record range, segment
hash, count), and re-chains the remainder behind that anchor.

Reads that cross the boundary load the segment when it is present. A missing
segment is reported **present-but-unavailable**, never as empty; a segment whose
hash disagrees with the anchor is surfaced as a break. Un-archiving (restore)
consumes the anchor and reintroduces the range, recorded.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)
from agentwatch.store import (
    GENESIS_HASH,
    MARKER_PRODUCER,
    RecordStore,
    _entry_hash,
)

ARCHIVE_ANCHOR_TOOL = "archive-anchor"
ARCHIVE_RESTORED_TOOL = "archive-restored"
ARCHIVE_DIR = "archives"


@dataclass(frozen=True)
class ArchiveAnchor:
    """The metadata-only anchor left in the live store."""

    segment_id: str
    file: str
    first_seq: int
    last_seq: int
    count: int
    segment_hash: str
    seq: int
    at: datetime


@dataclass(frozen=True)
class ArchiveReport:
    """Outcome of an archive command."""

    archived: int
    segment_id: str
    segment_path: Path
    anchor_seq: int
    remaining: int


@dataclass(frozen=True)
class ArchiveVerdict:
    """Independent verification of one segment."""

    segment_id: str
    file: str
    available: bool
    ok: bool
    detail: str


@dataclass(frozen=True)
class ArchivedRecords:
    """Records read across the archive boundary, plus unavailable segment ids."""

    records: tuple[AgentRecord, ...]
    unavailable: tuple[str, ...]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _has_format_marker(lines: list[str]) -> bool:
    if not lines:
        return False
    try:
        payload = json.loads(lines[0])
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and "format" in payload and "seq" not in payload


def _anchor_record(
    *,
    segment_id: str,
    file: str,
    first_seq: int,
    last_seq: int,
    count: int,
    segment_hash: str,
    moment: datetime,
) -> AgentRecord:
    return AgentRecord(
        session_id="agentwatch",
        agent=AgentIdentity(identity="agentwatch"),
        tool=ToolCall(
            name=ARCHIVE_ANCHOR_TOOL,
            arguments={
                "segment_id": segment_id,
                "file": file,
                "first_seq": first_seq,
                "last_seq": last_seq,
                "count": count,
                "segment_hash": segment_hash,
            },
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
        outcome=Outcome.OK,
        started_at=moment,
        producer=MARKER_PRODUCER,
    )


def _cut_index(entries: list[Any], before: datetime) -> int:
    """The number of leading entries at/older than ``before`` (contiguous).

    A leading tombstone/checkpoint has no timestamp of its own but is by
    definition old (it was purged because it aged out), so it is archivable
    before the first live record; later ones inherit the running live timestamp.
    """
    current: datetime | None = None
    cut = 0
    seen_live = False
    for index, entry in enumerate(entries):
        if entry.record is not None:
            seen_live = True
            if entry.record.started_at >= before:
                break
            current = entry.record.started_at
            cut = index + 1
        elif not seen_live or current is not None and current < before:
            cut = index + 1
        else:
            break
    return cut


def archive_store(
    store: RecordStore,
    store_path: Path | str,
    *,
    before: datetime,
    out_dir: Path | str | None = None,
    now: datetime | None = None,
) -> ArchiveReport:
    """Move the chain prefix older than ``before`` into a sealed segment.

    The remainder is re-chained behind a single anchor record. The segment is a
    byte-identical prefix of the original store, so the same verifier (S12) checks
    it independently.
    """
    path = Path(store_path)
    entries = store.entries()
    cut = _cut_index(entries, before)
    if cut == 0:
        raise ValueError("no entries older than the requested boundary")

    destination = Path(out_dir).expanduser() if out_dir is not None else path.parent / ARCHIVE_DIR
    destination.mkdir(parents=True, exist_ok=True)

    original = path.read_text(encoding="utf-8").splitlines()
    offset = 1 if _has_format_marker(original) else 0
    segment_lines = original[: cut + offset]  # format marker (if any) + archived envelopes
    segment_bytes = ("\n".join(segment_lines) + "\n").encode("utf-8")
    segment_hash = _sha256(segment_bytes)
    moment = now or datetime.now(timezone.utc)
    stamp = moment.strftime("%Y%m%dT%H%M%SZ")
    segment_id = f"seg-{stamp}-{segment_hash[:12]}"
    file_name = f"{segment_id}.jsonl"
    segment_path = destination / file_name
    segment_path.write_bytes(segment_bytes)
    os.chmod(segment_path, 0o600)

    kept = entries[cut:]
    anchor = _anchor_record(
        segment_id=segment_id,
        file=file_name,
        first_seq=0,
        last_seq=cut - 1,
        count=cut,
        segment_hash=segment_hash,
        moment=moment,
    )
    lines = [json.dumps({"format": store.format})]
    anchor_payload = anchor.to_dict()
    anchor_hash = _entry_hash(GENESIS_HASH, anchor_payload)
    lines.append(
        json.dumps(
            {
                "seq": 0,
                "prev_hash": GENESIS_HASH,
                "hash": anchor_hash,
                "record": anchor_payload,
            }
        )
    )
    prev = anchor_hash
    seq = 1
    for entry in kept:
        line, prev = _rechain(seq, prev, entry)
        lines.append(line)
        seq += 1
    tmp = path.with_name(path.name + ".archive.tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    store.reload()
    return ArchiveReport(
        archived=cut,
        segment_id=segment_id,
        segment_path=segment_path,
        anchor_seq=0,
        remaining=len(kept),
    )


def _rechain(seq: int, prev_hash: str, entry: Any) -> tuple[str, str]:
    if entry.checkpoint:
        payload = {"checkpoint": True, "entries": entry.entries or 0, "at": entry.at or ""}
        digest = _entry_hash(prev_hash, payload)
        line = json.dumps(
            {
                "seq": seq,
                "prev_hash": prev_hash,
                "hash": digest,
                "checkpoint": True,
                "entries": payload["entries"],
                "at": payload["at"],
            }
        )
        return line, digest
    if entry.tombstone or entry.record is None:
        payload = {"tombstone": True}
        digest = _entry_hash(prev_hash, payload)
        line = json.dumps({"seq": seq, "prev_hash": prev_hash, "hash": digest, "tombstone": True})
        return line, digest
    record = entry.record.to_dict()
    digest = _entry_hash(prev_hash, record)
    line = json.dumps({"seq": seq, "prev_hash": prev_hash, "hash": digest, "record": record})
    return line, digest


def _consumed_segment_ids(store: RecordStore) -> set[str]:
    consumed: set[str] = set()
    for record in store.records():
        if record.tool.name == ARCHIVE_RESTORED_TOOL and record.tool.arguments is not None:
            consumed.add(str(record.tool.arguments.get("segment_id", "")))
    return consumed


def archive_anchors(store: RecordStore, *, include_consumed: bool = False) -> list[ArchiveAnchor]:
    """Every live anchor record, in store order.

    An anchor consumed by :func:`restore_archive` is skipped unless
    ``include_consumed`` is set, so a restored range is never read twice.
    """
    consumed = set() if include_consumed else _consumed_segment_ids(store)
    anchors: list[ArchiveAnchor] = []
    for entry in store.entries():
        record = entry.record
        if record is None or record.tool.name != ARCHIVE_ANCHOR_TOOL:
            continue
        arguments = record.tool.arguments or {}
        if str(arguments.get("segment_id", "")) in consumed:
            continue
        anchors.append(
            ArchiveAnchor(
                segment_id=str(arguments.get("segment_id", "")),
                file=str(arguments.get("file", "")),
                first_seq=int(arguments.get("first_seq", 0)),
                last_seq=int(arguments.get("last_seq", 0)),
                count=int(arguments.get("count", 0)),
                segment_hash=str(arguments.get("segment_hash", "")),
                seq=entry.seq,
                at=record.started_at,
            )
        )
    return anchors


def _segment_path(store_dir: Path, anchor: ArchiveAnchor) -> Path:
    return store_dir / ARCHIVE_DIR / anchor.file


def load_segment(
    store_dir: Path | str, anchor: ArchiveAnchor
) -> tuple[RecordStore | None, ArchiveVerdict]:
    """Load and independently verify one segment, or explain why it is unavailable."""
    path = _segment_path(Path(store_dir).expanduser(), anchor)
    if not path.exists():
        return None, ArchiveVerdict(
            anchor.segment_id, anchor.file, False, False, "present-but-unavailable"
        )
    if _sha256(path.read_bytes()) != anchor.segment_hash:
        return None, ArchiveVerdict(
            anchor.segment_id, anchor.file, True, False, "segment hash disagrees with anchor"
        )
    segment = RecordStore(path)
    status = segment.verify()
    if not status.ok:
        return None, ArchiveVerdict(
            anchor.segment_id,
            anchor.file,
            True,
            False,
            f"segment chain broken at seq {status.broken_at}",
        )
    return segment, ArchiveVerdict(
        anchor.segment_id, anchor.file, True, True, f"ok ({status.checked} entries)"
    )


def verify_archives(store: RecordStore, store_dir: Path | str) -> list[ArchiveVerdict]:
    """Verify every archive segment referenced by the live store."""
    return [load_segment(store_dir, anchor)[1] for anchor in archive_anchors(store)]


def combined_records(store: RecordStore, store_dir: Path | str) -> ArchivedRecords:
    """Live records plus every available, verified archived record.

    A missing or broken segment is listed in ``unavailable`` and never silently
    treated as empty.
    """
    records: list[AgentRecord] = [
        record
        for record in store.records()
        if record.tool.name not in (ARCHIVE_ANCHOR_TOOL, ARCHIVE_RESTORED_TOOL)
    ]
    unavailable: list[str] = []
    for anchor in archive_anchors(store):
        segment, verdict = load_segment(store_dir, anchor)
        if segment is None:
            unavailable.append(verdict.segment_id)
            continue
        records.extend(segment.records())
    return ArchivedRecords(records=tuple(records), unavailable=tuple(unavailable))


def restore_archive(
    store: RecordStore, store_dir: Path | str, *, segment_id: str, now: datetime | None = None
) -> int:
    """Reintroduce an archived range and consume its anchor (recorded as an anchor).

    Returns the number of records restored. The consumed anchor is replaced by a
    ``restore`` marker so the operation is itself in the chain.
    """
    anchor = next(
        (a for a in archive_anchors(store, include_consumed=True) if a.segment_id == segment_id),
        None,
    )
    if anchor is None:
        raise ValueError(f"no archive anchor for segment {segment_id}")
    segment, verdict = load_segment(store_dir, anchor)
    if segment is None:
        raise ValueError(f"archive {segment_id} is {verdict.detail}; cannot restore")
    restored = 0
    for record in segment.records():
        store.append(record)
        restored += 1
    moment = now or datetime.now(timezone.utc)
    store.append(
        AgentRecord(
            session_id="agentwatch",
            agent=AgentIdentity(identity="agentwatch"),
            tool=ToolCall(
                name=ARCHIVE_RESTORED_TOOL,
                arguments={"segment_id": segment_id, "records": restored},
                privacy_mode=RecordPrivacyMode.METADATA_ONLY,
            ),
            outcome=Outcome.OK,
            started_at=moment,
            producer=MARKER_PRODUCER,
        )
    )
    return restored
