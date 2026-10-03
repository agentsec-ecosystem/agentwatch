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
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agentwatch.records import AgentRecord, RecordValidationError, validate_record

GENESIS_HASH = "0" * 64
_BYTES_PER_MB = 1024 * 1024


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
    line: int | None = None


class ChainError(Exception):
    """Raised by callers that require an intact chain."""


class StoreFullError(Exception):
    """Raised when the size cap is reached: recording stops, never overwrites (F3)."""


@dataclass(frozen=True)
class RetentionReport:
    """Outcome of a retention pass."""

    purged: int
    kept: int


class RecordStore:
    """Append-only JSONL store with a hash chain over its entries."""

    def __init__(self, path: Path | str, *, max_size_mb: int | None = None) -> None:
        self.path = Path(path)
        self.max_size_mb = max_size_mb
        self.parse_errors: list[int] = []
        self.parse_error_lines: list[int] = []
        self._entries: list[ChainEntry] = self._load()
        self._lock = threading.Lock()

    # -- reading -----------------------------------------------------------

    def _load(self) -> list[ChainEntry]:
        self.parse_errors = []
        self.parse_error_lines = []
        entries: list[ChainEntry] = []
        if not self.path.exists():
            return entries
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").split("\n"), start=1
        ):
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
                self.parse_error_lines.append(line_number)
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
            return ChainStatus(
                ok=False,
                checked=len(entries),
                broken_at=self.parse_errors[0],
                line=self.parse_error_lines[0] if self.parse_error_lines else None,
            )
        prev = GENESIS_HASH
        for expected_seq, entry in enumerate(entries):
            if entry.seq != expected_seq or entry.prev_hash != prev:
                return ChainStatus(ok=False, checked=len(entries), broken_at=entry.seq)
            if (
                not entry.tombstone
                and entry.record is not None
                and _entry_hash(entry.prev_hash, entry.record.to_dict()) != entry.hash
            ):
                return ChainStatus(ok=False, checked=len(entries), broken_at=entry.seq)
            prev = entry.hash
        return ChainStatus(ok=True, checked=len(entries), broken_at=None)

    # -- writing -----------------------------------------------------------

    def append(self, record: AgentRecord) -> ChainEntry:
        """Append one record, computing and storing its chain hash.

        Serialized by an in-process lock so concurrent writers (the daemon's
        serve/sweeper/stop threads) cannot interleave or reuse a ``seq``.

        Raises:
            StoreFullError: when the configured size cap is already reached
                (F3) — recording stops and is surfaced, nothing is overwritten.
        """
        with self._lock:
            if (
                self.max_size_mb is not None
                and self.size_bytes() >= self.max_size_mb * _BYTES_PER_MB
            ):
                raise StoreFullError(
                    f"store {self.path} reached the {self.max_size_mb} MB cap; "
                    "raise store.max_size_mb or run retention"
                )
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
            # A crash can leave a partial line with no trailing newline; start a
            # new line so the next valid record is not concatenated onto it.
            needs_separator = self._ends_without_newline()
            with self.path.open("a", encoding="utf-8") as handle:
                if needs_separator:
                    handle.write("\n")
                handle.write(json.dumps(envelope, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            entry = ChainEntry(
                seq=seq, prev_hash=prev_hash, hash=str(envelope["hash"]), record=record
            )
            self._entries.append(entry)
            return entry

    def _ends_without_newline(self) -> bool:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return False
        with self.path.open("rb") as handle:
            handle.seek(-1, os.SEEK_END)
            return handle.read(1) != b"\n"

    def apply_retention(
        self, *, retention_days: int, now: datetime | None = None
    ) -> RetentionReport:
        """Tombstone entries older than the window; never remove a line silently.

        Tombstones keep ``seq``/``prev_hash``/``hash`` so the chain links still
        verify; only the record payload is dropped. Future-dated entries (clock
        skew) are kept (Review Focus 3).
        """
        with self._lock:
            moment = now or datetime.now(timezone.utc)
            cutoff = moment - timedelta(days=retention_days)
            lines: list[str] = []
            purged = 0
            kept = 0
            for entry in self._entries:
                if (
                    not entry.tombstone
                    and entry.record is not None
                    and entry.record.started_at < cutoff
                ):
                    purged += 1
                    lines.append(
                        json.dumps(
                            {
                                "seq": entry.seq,
                                "prev_hash": entry.prev_hash,
                                "hash": entry.hash,
                                "tombstone": True,
                                "purged_at": moment.isoformat(),
                            },
                            ensure_ascii=False,
                        )
                    )
                    continue
                kept += 1
                payload = entry.record.to_dict() if entry.record is not None else None
                lines.append(
                    json.dumps(
                        {
                            "seq": entry.seq,
                            "prev_hash": entry.prev_hash,
                            "hash": entry.hash,
                            "tombstone": entry.tombstone,
                            "record": payload,
                        },
                        ensure_ascii=False,
                    )
                )
            if purged:
                # Atomic rewrite under the append lock; a no-op pass leaves the file byte-identical.
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_name(self.path.name + ".tmp")
                tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
                os.replace(tmp, self.path)
                self._entries = self._load()
            return RetentionReport(purged=purged, kept=kept)
