"""Live tail + back-fill reconciliation (M26 STR-2, PRD 42).

The store is the source of truth; a stream (the STR-1 transport) only *notifies*
by sequence number. When a notification is dropped (a backpressured subscriber)
or missed (a late join, a rotated file), the consumer **back-fills** the missing
records from the store and classifies every gap, so the live view never diverges
from the chain. A backpressured subscriber keeps ``degraded`` visible.

``LiveTail`` works in two modes:

* **subscriber mode** — drains seq notifications from a
  :class:`agentwatch.streaming.Subscriber` (what the daemon publishes); the
  payload always comes from the store.
* **file mode** — reads new seqs from the store file cursor (for ``tail -f
  --reconcile``); a detected rotation triggers a store catch-up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from agentwatch.records import AgentRecord
from agentwatch.store import ChainEntry, RecordStore
from agentwatch.streaming import Subscriber
from agentwatch.tail import TailLine, render_record

# Gap kinds, classified — never a bare "unknown".
GAP_STREAM_DROP = "stream-drop"
GAP_PURGED = "purged"
GAP_MISSING = "missing"
GAP_ROTATED = "rotated"


@dataclass(frozen=True)
class LiveGap:
    """One classified gap in the live stream (a range of seqs)."""

    kind: str
    from_seq: int
    to_seq: int
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "from_seq": self.from_seq,
            "to_seq": self.to_seq,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class LiveBatch:
    """One poll's rendered lines, classified gaps, and degraded state."""

    lines: tuple[TailLine, ...]
    gaps: tuple[LiveGap, ...]
    degraded: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "degraded": self.degraded,
            "lines": [line.text for line in self.lines],
            "gaps": [gap.to_dict() for gap in self.gaps],
        }


class LiveTail:
    """A store-truth live tail that back-fills dropped/missed notifications."""

    def __init__(
        self,
        path: Path | str,
        *,
        subscriber: Subscriber[int] | None = None,
        session_id: str | None = None,
        project: str | None = None,
        first_seq: int = 0,
    ) -> None:
        self.path = Path(path)
        self.subscriber = subscriber
        self.session_id = session_id
        self.project = project
        self._next = first_seq
        self._offset = 0
        self._buffer = ""

    # -- notification sources ---------------------------------------------

    def attach(self, subscriber: Subscriber[int] | None) -> None:
        """Point the tail at a new subscriber (consumer restart/reconnect)."""
        self.subscriber = subscriber

    def _drain_subscriber(self) -> list[int]:
        assert self.subscriber is not None
        seqs: list[int] = []
        while True:
            item = self.subscriber.get(timeout=0)
            if item is None:
                return seqs
            seqs.append(item)

    def _read_file_seqs(self) -> tuple[list[int], bool]:
        """New seqs from the store file cursor, plus whether a rotation was seen."""
        if not self.path.exists():
            return [], False
        try:
            with self.path.open("rb") as handle:
                size = handle.seek(0, 2)
                rotated = size < self._offset
                if rotated:
                    self._offset = 0
                    self._buffer = ""
                handle.seek(self._offset)
                chunk = handle.read()
                self._offset = handle.tell()
        except OSError:
            return [], False
        self._buffer += chunk.decode("utf-8", errors="replace")
        complete = self._buffer.split("\n")
        self._buffer = complete.pop()
        seqs: list[int] = []
        for raw in complete:
            if not raw.strip():
                continue
            try:
                envelope = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(envelope, dict) and isinstance(envelope.get("seq"), int):
                seqs.append(envelope["seq"])
        return seqs, rotated

    # -- reconciliation ----------------------------------------------------

    def _emit(
        self,
        entry: ChainEntry | None,
        seq: int,
        lines: list[TailLine],
        gaps: list[LiveGap],
    ) -> bool:
        """Emit one entry's line; return whether a line was emitted (filters aside)."""
        if entry is None:
            gaps.append(LiveGap(GAP_MISSING, seq, seq, "no chain entry for seq"))
            return False
        if entry.tombstone or entry.record is None:
            gaps.append(LiveGap(GAP_PURGED, seq, seq, "tombstoned (purged/retained)"))
            return False
        record: AgentRecord = entry.record
        if self.session_id is not None and record.session_id != self.session_id:
            return False
        if self.project is not None and record.project != self.project:
            return False
        lines.append(TailLine(render_record(record), record=record))
        return True

    def _backfill(
        self,
        seq: int,
        entries: dict[int, ChainEntry],
        lines: list[TailLine],
        gaps: list[LiveGap],
        *,
        kind: str = GAP_STREAM_DROP,
    ) -> None:
        entry = entries.get(seq)
        if entry is None or entry.tombstone or entry.record is None:
            self._emit(entry, seq, lines, gaps)
            return
        if self._emit(entry, seq, lines, gaps):
            gaps.append(LiveGap(kind, seq, seq, "notified late; back-filled from the store"))

    def poll(self) -> LiveBatch:
        """Reconcile one poll into lines + classified gaps + degraded state."""
        degraded = self.subscriber.overflowed if self.subscriber is not None else False
        rotated = False
        if self.subscriber is not None:
            observed = self._drain_subscriber()
        else:
            observed, rotated = self._read_file_seqs()
        degraded = degraded or rotated

        store = RecordStore(self.path)
        entries: dict[int, ChainEntry] = {entry.seq: entry for entry in store.entries()}
        lines: list[TailLine] = []
        gaps: list[LiveGap] = []

        if rotated:
            # The file was replaced/truncated; catch up to the store's head.
            gaps.append(LiveGap(GAP_ROTATED, self._next, self._next, "store file rotated"))
            observed = sorted(entry for entry in entries if entry >= self._next)

        for seq in sorted(set(observed)):
            if seq < self._next:
                continue
            while self._next < seq:
                self._backfill(self._next, entries, lines, gaps)
                self._next += 1
            self._emit(entries.get(seq), seq, lines, gaps)
            self._next = seq + 1

        if degraded and entries:
            # A backpressured subscriber lost notifications we were never told
            # about; catch up to the store head, classifying each back-fill.
            head = max(entries)
            while self._next <= head:
                self._backfill(self._next, entries, lines, gaps)
                self._next += 1
        return LiveBatch(lines=tuple(lines), gaps=tuple(gaps), degraded=degraded)


__all__ = [
    "GAP_MISSING",
    "GAP_PURGED",
    "GAP_ROTATED",
    "GAP_STREAM_DROP",
    "LiveBatch",
    "LiveGap",
    "LiveTail",
]
