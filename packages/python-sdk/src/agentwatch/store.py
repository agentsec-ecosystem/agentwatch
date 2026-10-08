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
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agentwatch import posture
from agentwatch.protocol import GENESIS_PREV_HASH, STORE_FORMAT_VERSION
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    Producer,
    ProducerKind,
    RecordPrivacyMode,
    RecordValidationError,
    ToolCall,
    validate_record,
)

GENESIS_HASH = GENESIS_PREV_HASH
_BYTES_PER_MB = 1024 * 1024

# Metadata-only marker records are agentwatch-authored (M15 S26).
MARKER_PRODUCER = Producer(kind=ProducerKind.SDK, name="agentwatch")

# Adaptive durability (M12 K1): an explicit, surfaced fsync policy.
DURABILITY_MODES = ("record", "checkpoint", "none")
DEFAULT_DURABILITY = "record"


def _canonical(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _entry_hash(prev_hash: str, record: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + _canonical(record)).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChainEntry:
    """One line of the store: a live record, a tombstone, or a chain checkpoint."""

    seq: int
    prev_hash: str
    hash: str
    record: AgentRecord | None
    tombstone: bool = False
    checkpoint: bool = False
    entries: int | None = None
    at: str | None = None


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
    held: int = 0
    dry_run: bool = False
    leftovers: tuple[str, ...] = ()


@dataclass(frozen=True)
class PurgeReport:
    """Outcome of a single-session purge (right to erasure)."""

    purged: int
    found: bool
    marker_seq: int | None
    blocked_by_hold: str | None = None
    override_reason: str | None = None
    leftovers: tuple[str, ...] = ()

    @property
    def override_required(self) -> bool:
        """Whether an active hold refused the purge (an override is needed)."""
        return self.blocked_by_hold is not None


@dataclass(frozen=True)
class RepairReport:
    """Outcome of an operator-initiated store repair (F4)."""

    broken_at: int | None
    salvaged: int
    dropped: int
    evidence_path: Path | None
    repaired: bool


class RecordStore:
    """Append-only JSONL store with a hash chain over its entries."""

    def __init__(
        self,
        path: Path | str,
        *,
        max_size_mb: int | None = None,
        durability: str = DEFAULT_DURABILITY,
        checkpoint_every: int | None = None,
    ) -> None:
        if durability not in DURABILITY_MODES:
            raise ValueError(
                f"unknown durability {durability!r}; expected one of {', '.join(DURABILITY_MODES)}"
            )
        if checkpoint_every is not None and checkpoint_every < 1:
            raise ValueError("checkpoint_every must be >= 1")
        self.path = Path(path)
        self.max_size_mb = max_size_mb
        self.durability = durability
        self.checkpoint_every = checkpoint_every
        self.format = STORE_FORMAT_VERSION
        self.unsupported_format = False
        self.parse_errors: list[int] = []
        self.parse_error_lines: list[int] = []
        self._entries: list[ChainEntry] = self._load()
        self._data_since_checkpoint = 0
        self._recount()
        self._lock = threading.RLock()

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
                if not isinstance(envelope, dict):
                    raise ValueError("not an envelope")
                if "format" in envelope and "seq" not in envelope:
                    self.format = int(envelope["format"])
                    if self.format != STORE_FORMAT_VERSION:
                        self.unsupported_format = True
                    continue
                if "seq" not in envelope:
                    raise ValueError("not an envelope")
                if envelope.get("checkpoint"):
                    entries.append(
                        ChainEntry(
                            seq=int(envelope["seq"]),
                            prev_hash=str(envelope.get("prev_hash", "")),
                            hash=str(envelope["hash"]),
                            record=None,
                            checkpoint=True,
                            entries=int(envelope.get("entries", 0)),
                            at=str(envelope.get("at", "")),
                        )
                    )
                    continue
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

    def checkpoints(self) -> list[ChainEntry]:
        """The chain checkpoints in order."""
        return [entry for entry in self._entries if entry.checkpoint]

    def _recount(self) -> None:
        """Count data entries since the last checkpoint (for auto-checkpointing)."""
        since = 0
        for entry in self._entries:
            since = 0 if entry.checkpoint else since + 1
        self._data_since_checkpoint = since

    def size_bytes(self) -> int:
        return self.path.stat().st_size if self.path.exists() else 0

    def refresh(self) -> ChainStatus:
        """Reload from disk and re-verify (continuous verification, M12 G2).

        The file read and O(n) chain verification run **outside** the store
        lock so concurrent ``append`` calls (the daemon's hot path) are not
        blocked while the sweep re-checks thousands of entries.  The store
        file is append-only; a concurrent append may add a line we miss this
        cycle — it is caught on the next sweep.  We only adopt the
        disk-loaded entry list when it is at least as long as the in-memory
        list, so a just-appended entry whose write has not landed on disk
        yet cannot cause ``append`` to reuse a ``seq`` (duplicate-seq chain
        break).
        """
        entries = self._load()
        status = self._verify_entries(entries)
        with self._lock:
            if len(entries) >= len(self._entries):
                self._entries = entries
            self._recount()
        return status

    def reload(self) -> ChainStatus:
        """Reload from disk and re-verify, adopting the on-disk chain unconditionally.

        For maintenance operations that **rewrite** the store (archive sealing),
        where the resulting chain is intentionally *shorter* than the in-memory
        list. ``refresh`` is append-aware and refuses to shrink; this method is
        the explicit "trust the file" reload for rewrite paths.
        """
        entries = self._load()
        status = self._verify_entries(entries)
        with self._lock:
            self._entries = entries
            self._recount()
        return status

    def _verify_entries(self, entries: list[ChainEntry]) -> ChainStatus:
        """Recompute the chain over a snapshot and report the first break (F4)."""
        if self.unsupported_format:
            return ChainStatus(ok=False, checked=len(entries), broken_at=None, line=1)
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
            if entry.checkpoint:
                payload = {
                    "checkpoint": True,
                    "entries": entry.entries,
                    "at": entry.at,
                }
                if _entry_hash(entry.prev_hash, payload) != entry.hash:
                    return ChainStatus(ok=False, checked=len(entries), broken_at=entry.seq)
            elif (
                not entry.tombstone
                and entry.record is not None
                and _entry_hash(entry.prev_hash, entry.record.to_dict()) != entry.hash
            ):
                return ChainStatus(ok=False, checked=len(entries), broken_at=entry.seq)
            prev = entry.hash
        return ChainStatus(ok=True, checked=len(entries), broken_at=None)

    def verify(self) -> ChainStatus:
        """Recompute the chain and report the first break (F4), never raising."""
        with self._lock:
            return self._verify_entries(self._entries)

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
            posture.secure_dir(self.path.parent)
            new_file = not self.path.exists() or self.path.stat().st_size == 0
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
                if new_file:
                    handle.write(json.dumps({"format": self.format}) + "\n")
                if needs_separator:
                    handle.write("\n")
                handle.write(json.dumps(envelope, ensure_ascii=False) + "\n")
                handle.flush()
                self._fsync_if(handle, per_record=True)
            if new_file:
                posture.secure_file(self.path)
            entry = ChainEntry(
                seq=seq, prev_hash=prev_hash, hash=str(envelope["hash"]), record=record
            )
            self._entries.append(entry)
            self._data_since_checkpoint += 1
            if (
                self.checkpoint_every is not None
                and self._data_since_checkpoint >= self.checkpoint_every
            ):
                self._append_checkpoint()
            return entry

    def _fsync_if(self, handle: Any, *, per_record: bool) -> None:
        """fsync per the durability policy (M12 K1)."""
        if self.durability == "none":
            return
        if self.durability == "record" or not per_record:
            os.fsync(handle.fileno())

    def _append_checkpoint(self) -> ChainEntry:
        """Append a chain checkpoint and reset the auto-checkpoint counter."""
        prev_hash = self._entries[-1].hash if self._entries else GENESIS_HASH
        seq = self._entries[-1].seq + 1 if self._entries else 0
        moment = datetime.now(timezone.utc).isoformat()
        covered = len(self._entries)
        payload = {"checkpoint": True, "entries": covered, "at": moment}
        envelope = {
            "seq": seq,
            "prev_hash": prev_hash,
            "hash": _entry_hash(prev_hash, payload),
            "checkpoint": True,
            "entries": covered,
            "at": moment,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope, ensure_ascii=False) + "\n")
            handle.flush()
            self._fsync_if(handle, per_record=False)
        posture.secure_file(self.path)
        entry = ChainEntry(
            seq=seq,
            prev_hash=prev_hash,
            hash=str(envelope["hash"]),
            record=None,
            checkpoint=True,
            entries=covered,
            at=moment,
        )
        self._entries.append(entry)
        self._data_since_checkpoint = 0
        return entry

    def checkpoint(self) -> ChainEntry:
        """Append a chain checkpoint on demand (M12 E1)."""
        with self._lock:
            return self._append_checkpoint()

    def close(self) -> None:
        """Flush durability state (fsync when the policy is ``checkpoint``/``record``)."""
        if not self.path.exists():
            return
        with self.path.open("ab") as handle:
            self._fsync_if(handle, per_record=False)

    def _ends_without_newline(self) -> bool:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return False
        with self.path.open("rb") as handle:
            handle.seek(-1, os.SEEK_END)
            return handle.read(1) != b"\n"

    def apply_retention(
        self,
        *,
        retention_days: int,
        now: datetime | None = None,
        dry_run: bool = False,
    ) -> RetentionReport:
        """Tombstone entries older than the window; never remove a line silently.

        Tombstones keep ``seq``/``prev_hash``/``hash`` so the chain links still
        verify; only the record payload is dropped. Future-dated entries (clock
        skew) are kept (Review Focus 3). Records protected by an active legal hold
        are **skipped** (HLD-1) and counted in ``held``; ``dry_run`` computes the
        same report without rewriting the store.
        """
        # Deferred import: holds reads this store; importing at module load would cycle.
        from agentwatch import holds as holds_module

        with self._lock:
            moment = now or datetime.now(timezone.utc)
            cutoff = moment - timedelta(days=retention_days)
            active = holds_module.active_holds(self)
            lines: list[str] = []
            purged = 0
            kept = 0
            held = 0
            for entry in self._entries:
                record = entry.record
                if not entry.tombstone and record is not None and record.started_at < cutoff:
                    if active and holds_module.record_is_held(record, active):
                        held += 1
                        kept += 1
                        if not dry_run:
                            lines.append(
                                json.dumps(
                                    {
                                        "seq": entry.seq,
                                        "prev_hash": entry.prev_hash,
                                        "hash": entry.hash,
                                        "tombstone": False,
                                        "record": record.to_dict(),
                                    },
                                    ensure_ascii=False,
                                )
                            )
                        continue
                    purged += 1
                    if not dry_run:
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
                if not dry_run:
                    payload = record.to_dict() if record is not None else None
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
            if purged and not dry_run:
                # Atomic rewrite under the append lock; a no-op pass leaves the file byte-identical.
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_name(self.path.name + ".tmp")
                tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
                os.replace(tmp, self.path)
                self._entries = self._load()
                self._propagate_retention()
            return RetentionReport(
                purged=purged,
                kept=kept,
                held=held,
                dry_run=dry_run,
                leftovers=() if dry_run else self._leftovers(),
            )

    def purge_session(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
        reason: str | None = None,
        override_reason: str | None = None,
    ) -> PurgeReport:
        """Tombstone every live record of one session; append a purge marker.

        Chain links are preserved (D-K: tombstone, never hard delete). The
        marker is a metadata-only record so the erasure is auditable. A session
        with no live records is a no-op (no marker written).

        An active legal hold (HLD-1) makes purge **fail closed**: nothing is
        tombstoned, the refusal is recorded, and ``blocked_by_hold`` names the
        hold. An explicit ``override_reason`` records the override and proceeds.
        """
        # Deferred import: holds reads this store; importing at module load would cycle.
        from agentwatch import holds as holds_module

        with self._lock:
            moment = now or datetime.now(timezone.utc)
            matched = [
                entry
                for entry in self._entries
                if not entry.tombstone
                and entry.record is not None
                and entry.record.session_id == session_id
            ]
            if not matched:
                return PurgeReport(purged=0, found=False, marker_seq=None)

            active = holds_module.active_holds(self)
            blocking = sorted(
                {
                    hold_id
                    for entry in matched
                    if entry.record is not None
                    for hold_id in holds_module.held_hold_ids(entry.record, active)
                }
            )
            if blocking and not override_reason:
                holds_module.record_purge_blocked(self, session_id, blocking[0], now=moment)
                return PurgeReport(
                    purged=0,
                    found=True,
                    marker_seq=None,
                    blocked_by_hold=blocking[0],
                )

            lines: list[str] = []
            for entry in self._entries:
                if (
                    not entry.tombstone
                    and entry.record is not None
                    and entry.record.session_id == session_id
                ):
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
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
            os.replace(tmp, self.path)
            self._entries = self._load()

            if blocking and override_reason:
                holds_module.record_purge_override(
                    self,
                    session_id,
                    reason=override_reason,
                    hold_ids=tuple(blocking),
                    now=moment,
                )
            entry = self.append(
                self._purge_marker(session_id, moment, reason),
            )
            self._propagate_purge(session_id)
            return PurgeReport(
                purged=len(matched),
                found=True,
                marker_seq=entry.seq,
                override_reason=override_reason,
                leftovers=self._leftovers(),
            )

    @staticmethod
    def _purge_marker(session_id: str, moment: datetime, reason: str | None) -> AgentRecord:
        arguments: dict[str, Any] = {"session_id": session_id}
        if reason:
            arguments["reason"] = reason
        return AgentRecord(
            session_id=session_id,
            agent=AgentIdentity(identity="agentwatch"),
            tool=ToolCall(
                name="session-purge",
                arguments=arguments,
                privacy_mode=RecordPrivacyMode.METADATA_ONLY,
            ),
            outcome=Outcome.OK,
            started_at=moment,
            producer=MARKER_PRODUCER,
        )

    # -- derived-artifact propagation (M30 EXT-5) --------------------------

    def _propagate_purge(self, session_id: str) -> None:
        """Drop one session's rows from the derived index (never touches the chain).

        Deferred import: ``query_index`` reads this store, so importing it at
        module load would cycle. The chain remains authoritative; the index is
        only ever a projection.
        """
        from agentwatch import query_index

        index = query_index.QueryIndex(query_index.index_path_for_store(self.path))
        if index.exists:
            index.purge_session(session_id)

    def _propagate_retention(self) -> None:
        """Rebuild the derived index from the now-tombstoned chain (EXT-5)."""
        from agentwatch import query_index

        index = query_index.QueryIndex(query_index.index_path_for_store(self.path))
        if index.exists:
            index.rebuild(self)

    def _leftovers(self) -> tuple[str, ...]:
        """Known derived artifacts beside the store that may still retain data."""
        from agentwatch import query_index

        return tuple(
            f"{artifact.kind}:{artifact.path}"
            for artifact in query_index.derived_artifacts(self.path.parent)
        )


def _entry_line(entry: ChainEntry) -> str:
    """Serialize a chain entry back to its JSONL line."""
    if entry.checkpoint:
        return json.dumps(
            {
                "seq": entry.seq,
                "prev_hash": entry.prev_hash,
                "hash": entry.hash,
                "checkpoint": True,
                "entries": entry.entries,
                "at": entry.at,
            },
            ensure_ascii=False,
        )
    if entry.tombstone or entry.record is None:
        return json.dumps(
            {
                "seq": entry.seq,
                "prev_hash": entry.prev_hash,
                "hash": entry.hash,
                "tombstone": True,
            },
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "seq": entry.seq,
            "prev_hash": entry.prev_hash,
            "hash": entry.hash,
            "record": entry.record.to_dict(),
        },
        ensure_ascii=False,
    )


def repair_store(path: Path | str, *, now: datetime | None = None) -> RepairReport:
    """Rebuild a corrupt store from its intact prefix, preserving evidence (F4).

    The damaged file is copied aside byte-identically (``records.corrupt-<ts>``);
    a fresh chain is written from the entries *before* the first break, so
    ``verify()`` is green afterwards. Records at/after the break are dropped and
    counted — never silently.
    """
    store_path = Path(path)
    store = RecordStore(store_path)
    status = store.verify()
    if status.ok:
        return RepairReport(
            broken_at=None,
            salvaged=len(store.entries()),
            dropped=0,
            evidence_path=None,
            repaired=False,
        )
    broken = status.broken_at if status.broken_at is not None else 0
    moment = now or datetime.now(timezone.utc)
    evidence: Path | None = None
    if store_path.exists():
        stamp = moment.strftime("%Y%m%dT%H%M%SZ")
        evidence = store_path.with_name(f"{store_path.name}.corrupt-{stamp}")
        shutil.copy2(store_path, evidence)

    keep = [entry for entry in store.entries() if entry.seq < broken]
    dropped = len(store.entries()) - len(keep)
    lines = [json.dumps({"format": STORE_FORMAT_VERSION})]
    lines.extend(_entry_line(entry) for entry in keep)
    posture.secure_dir(store_path.parent)
    tmp = store_path.with_name(store_path.name + ".repair.tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, store_path)
    posture.secure_file(store_path)
    return RepairReport(
        broken_at=broken,
        salvaged=len(keep),
        dropped=dropped,
        evidence_path=evidence,
        repaired=True,
    )
