"""Append-only, hash-chained JSONL store (M4 4.3/4.4, DD-07/DD-08).

Local-first persistence for normalized records. Each line is an envelope::

    {"seq": N, "prev_hash": "...", "hash": "...", "record": {...}}

``hash`` is ``sha256(prev_hash + canonical_json(record))``, so any edit to a
record or a deleted line breaks the chain and is surfaced by :meth:`verify`
(F4) rather than silently trusted. Retention rewrites old entries as
*tombstones* that keep the chain links but drop the record payload.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentwatch.records import AgentRecord, RecordValidationError, validate_record

GENESIS_HASH = "0" * 64


def _canonical(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _entry_hash(prev_hash: str, record: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + _canonical(record)).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChainEntry:
    """One line of the store: a live record or a retention tombstone."""

    seq: int
    prev_hash: str
    hash: str
    record: AgentRecord | None
    tombstone: bool = False


@dataclass(frozen=True)
class ChainStatus:
    """Result of verifying the hash chain (never raises; reports F4)."""

    ok: bool
    checked: int
    broken_at: int | None


class ChainError(Exception):
    """Raised by callers that require an intact chain."""


class RecordStore:
    """Append-only JSONL store with a hash chain over its entries."""

    def __init__(self, path: Path | str, *, max_size_mb: int | None = None) -> None:
        self.path = Path(path)
        self.max_size_mb = max_size_mb
        self.parse_errors: list[int] = []
        self._entries: list[ChainEntry] = self._load()

    # -- reading -----------------------------------------------------------

    def _load(self) -> list[ChainEntry]:
        self.parse_errors = []
        entries: list[ChainEntry] = []
        if not self.path.exists():
            return entries
        for line in self.path.read_text(encoding="utf-8").split("\n"):
            if not line:
                continue
            try:
                envelope = json.loads(line)
                if not isinstance(envelope, dict) or "seq" not in envelope:
                    raise ValueError("not an envelope")
                record_data = envelope.get("record")
                tombstone = bool(envelope.get("tombstone", False))
                record = None
                if not tombstone and record_data is not None:
                    record = validate_record(record_data)
                entries.append(
                    ChainEntry(
                        seq=int(envelope["seq"]),
                        prev_hash=str(envelope.get("prev_hash", "")),
                        hash=str(envelope["hash"]),
                        record=record,
                        tombstone=tombstone,
                    )
                )
            except (json.JSONDecodeError, ValueError, KeyError, RecordValidationError, TypeError):
                self.parse_errors.append(entries[-1].seq + 1 if entries else 0)
        return entries

    def entries(self) -> list[ChainEntry]:
        return list(self._entries)

    def records(self) -> list[AgentRecord]:
        return [entry.record for entry in self._entries if entry.record is not None]

    def size_bytes(self) -> int:
        return self.path.stat().st_size if self.path.exists() else 0

    def verify(self) -> ChainStatus:
        """Recompute the chain and report the first break (F4), never raising."""
        entries = self._entries
        if self.parse_errors:
            return ChainStatus(ok=False, checked=len(entries), broken_at=self.parse_errors[0])
        prev = GENESIS_HASH
        for entry in entries:
            if entry.prev_hash != prev:
                return ChainStatus(ok=False, checked=len(entries), broken_at=entry.seq)
            if not entry.tombstone and entry.record is not None:
                if _entry_hash(entry.prev_hash, entry.record.to_dict()) != entry.hash:
                    return ChainStatus(ok=False, checked=len(entries), broken_at=entry.seq)
            prev = entry.hash
        return ChainStatus(ok=True, checked=len(entries), broken_at=None)

    # -- writing -----------------------------------------------------------

    def append(self, record: AgentRecord) -> ChainEntry:
        """Append one record, computing and storing its chain hash."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        seq = self._entries[-1].seq + 1 if self._entries else 0
        prev_hash = self._entries[-1].hash if self._entries else GENESIS_HASH
        record_data = record.to_dict()
        envelope = {
            "seq": seq,
            "prev_hash": prev_hash,
            "hash": _entry_hash(prev_hash, record_data),
            "record": record_data,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        entry = ChainEntry(seq=seq, prev_hash=prev_hash, hash=envelope["hash"], record=record)
        self._entries.append(entry)
        return entry
