"""Embedded, rebuildable query index (M30 LUI-2, PRD 54 §LUI-2, ADR-0035).

A **derived** index over the hash-chained JSONL store. The chain store remains
the sole source of truth (ADR-0019): the index can be deleted at any time with
no data loss, and rebuilt **bit-for-bit** from the chain by replaying entries in
order. It is a stdlib ``sqlite3`` artifact — the CLI, the console, and every
command keep working with **no heavyweight runtime dependency** (ADR-0035).

Design:

* ``records`` holds one row per live chain entry, keyed by the entry ``seq`` so
  rebuild order is deterministic. Indexed columns cover the common
  ``search``/``sessions`` filters; the full record JSON is kept for exact parity.
* Freshness is a digest of the chain *including tombstone state*, so a purge or
  retention pass (which rewrites an entry as a tombstone while keeping its hash)
  invalidates the index; the next use rebuilds it from the chain.
* Optional columnar export (``export_parquet``) imports ``pyarrow`` lazily and
  raises :class:`ParquetUnavailable` when the extra is not installed, so the
  core package stays dependency-light.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentwatch.query import search as _search_records
from agentwatch.records import AgentRecord, effective_producer, validate_record
from agentwatch.store import RecordStore

INDEX_FILENAME = "index.sqlite3"
INDEX_FORMAT_VERSION = 1
PARQUET_EXTRA = "agentwatch[parquet]"

_SCHEMA = """
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE records (
    seq INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    outcome TEXT NOT NULL,
    project TEXT,
    producer_kind TEXT,
    started_at TEXT NOT NULL,
    record TEXT NOT NULL
);
CREATE INDEX ix_records_session ON records(session_id);
CREATE INDEX ix_records_tool ON records(tool_name);
CREATE INDEX ix_records_started ON records(started_at);
"""

# Indexed columns that can be filtered in SQL before the Python filter runs.
_PRE_FILTERS = ("session_id", "tool", "outcome", "project", "producer")
_PRE_COLUMNS = {
    "session_id": "session_id",
    "tool": "tool_name",
    "outcome": "outcome",
    "project": "project",
    "producer": "producer_kind",
}


class ParquetUnavailableError(RuntimeError):
    """Raised when a parquet export is requested without the optional extra."""


@dataclass(frozen=True)
class IndexStatus:
    """What the index artifact on disk currently claims."""

    path: Path
    present: bool
    format_version: int | None = None
    records: int = 0
    source_signature: str | None = None


def index_path_for_store(store_path: Path | str) -> Path:
    """The index lives beside the store file (``<store>/records.jsonl``)."""
    return Path(store_path).parent / INDEX_FILENAME


def _canonical(record: Mapping[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class QueryIndex:
    """A sqlite-backed, derived projection of a :class:`RecordStore`."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    # -- lifecycle ---------------------------------------------------------

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    def drop(self) -> None:
        """Delete the index artifact (never the chain store)."""
        for suffix in ("", "-journal", "-wal", "-shm"):
            candidate = self.path.with_name(self.path.name + suffix)
            if candidate.exists():
                candidate.unlink()

    def status(self) -> IndexStatus:
        if not self.exists:
            return IndexStatus(path=self.path, present=False)
        try:
            connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
            try:
                meta = dict(connection.execute("SELECT key, value FROM meta"))
                count = int(connection.execute("SELECT COUNT(*) FROM records").fetchone()[0])
            finally:
                connection.close()
        except sqlite3.Error:
            return IndexStatus(path=self.path, present=True)
        try:
            version = int(meta.get("format_version", 0))
        except (TypeError, ValueError):
            version = None
        return IndexStatus(
            path=self.path,
            present=True,
            format_version=version,
            records=count,
            source_signature=meta.get("source_signature"),
        )

    def compute_signature(self, store: RecordStore) -> str:
        """A digest of the chain that also captures tombstone/checkpoint state.

        Chain hashes alone do not change when an entry is rewritten as a
        tombstone, so freshness must include the tombstone bit (EXT-5).
        """
        digest = hashlib.sha256()
        for entry in store.entries():
            if entry.checkpoint:
                marker = "C"
            elif entry.tombstone:
                marker = "T"
            else:
                marker = "L"
            digest.update(f"{entry.seq}:{entry.hash}:{marker}".encode())
            digest.update(b"\n")
        return digest.hexdigest()

    def is_fresh(self, store: RecordStore) -> bool:
        """Whether the on-disk index exactly reflects the current chain."""
        if not self.exists:
            return False
        status = self.status()
        if status.format_version != INDEX_FORMAT_VERSION:
            return False
        return status.source_signature == self.compute_signature(store)

    def ensure(self, store: RecordStore) -> IndexStatus:
        """Rebuild only when missing or stale; return the resulting status."""
        if not self.is_fresh(store):
            return self.rebuild(store)
        return self.status()

    # -- building ----------------------------------------------------------

    def rebuild(self, store: RecordStore) -> IndexStatus:
        """Reproject every live chain entry; deterministic and bit-for-bit."""
        rows = (
            _row(entry.seq, entry.record)
            for entry in store.entries()
            if entry.record is not None and not entry.tombstone
        )
        self.build_rows(rows, source_signature=self.compute_signature(store))
        return self.status()

    def build_rows(
        self, rows: Iterable[Mapping[str, Any]], *, source_signature: str = ""
    ) -> int:
        """Write a fresh index from projected rows (bulk, streaming).

        ``rows`` carry the projected columns plus ``record`` (canonical JSON).
        The artifact is built at a temp path and atomically moved into place so
        a crash never leaves a half-written index masquerading as fresh.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        if tmp.exists():
            tmp.unlink()
        count = 0
        connection = sqlite3.connect(tmp)
        try:
            connection.executescript(_SCHEMA)
            connection.execute("PRAGMA synchronous=OFF")
            payload = (
                (
                    row["seq"],
                    row["session_id"],
                    row["tool_name"],
                    row["outcome"],
                    row.get("project"),
                    row.get("producer_kind"),
                    row["started_at"],
                    row["record"],
                )
                for row in rows
            )
            connection.executemany(
                "INSERT INTO records (seq, session_id, tool_name, outcome, project, "
                "producer_kind, started_at, record) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                payload,
            )
            count = int(connection.execute("SELECT COUNT(*) FROM records").fetchone()[0])
            connection.executemany(
                "INSERT INTO meta (key, value) VALUES (?, ?)",
                (
                    ("format_version", str(INDEX_FORMAT_VERSION)),
                    ("source_signature", source_signature),
                ),
            )
            connection.commit()
        finally:
            connection.close()
        os.replace(tmp, self.path)
        return count

    # -- reading -----------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)

    def count(self) -> int:
        if not self.exists:
            return 0
        try:
            connection = self._connect()
            try:
                return int(connection.execute("SELECT COUNT(*) FROM records").fetchone()[0])
            finally:
                connection.close()
        except sqlite3.Error:
            return 0

    def sessions(self) -> list[str]:
        """Distinct session ids in first-appearance (seq) order."""
        if not self.exists:
            return []
        try:
            connection = self._connect()
            try:
                cursor = connection.execute(
                    "SELECT session_id FROM records GROUP BY session_id "
                    "ORDER BY MIN(seq)"
                )
                return [str(row[0]) for row in cursor]
            finally:
                connection.close()
        except sqlite3.Error:
            return []

    def candidates(self, **pre_filters: Any) -> list[AgentRecord]:
        """Records matching the SQL-indexed filters, in chain order.

        Returns ``[]`` when the index is absent or unreadable; callers fall back
        to the chain (the index is never authoritative).
        """
        if not self.exists:
            return []
        clauses: list[str] = []
        params: list[Any] = []
        for name, column in _PRE_COLUMNS.items():
            value = pre_filters.get(name)
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        try:
            connection = self._connect()
            try:
                cursor = connection.execute(
                    f"SELECT record FROM records{where} ORDER BY seq", params
                )
                rows = cursor.fetchall()
            finally:
                connection.close()
        except sqlite3.Error:
            return []
        return [validate_record(json.loads(row[0])) for row in rows]

    def search(self, store: RecordStore, **filters: Any) -> list[AgentRecord]:
        """Index-backed ``query.search`` with exact parity and chain fallback.

        When the index is fresh, the SQL-indexed filters narrow the candidate
        set; the identical Python filter then runs over those candidates. With
        no index (or a stale one) the search falls back to the chain — deleting
        the index never breaks a command, it only makes it slower.
        """
        permission_mode = filters.get("permission_mode")
        if self.is_fresh(store) and permission_mode is None:
            pre = {name: filters.get(name) for name in _PRE_FILTERS}
            records = self.candidates(**pre)
        else:
            records = None
        return _search_records(store, records=records, **filters)

    # -- maintenance -------------------------------------------------------

    def purge_session(self, session_id: str) -> int:
        """Drop one session's rows from the index (EXT-5); chain remains truth."""
        if not self.exists:
            return 0
        try:
            connection = sqlite3.connect(self.path)
            try:
                cursor = connection.execute(
                    "DELETE FROM records WHERE session_id = ?", (session_id,)
                )
                connection.commit()
                return int(cursor.rowcount)
            finally:
                connection.close()
        except sqlite3.Error:
            return 0

    # -- export ------------------------------------------------------------

    def export_parquet(self, path: Path | str, *, session_id: str | None = None) -> int:
        """Columnar export for notebooks/BI (optional ``parquet`` extra)."""
        try:
            import pyarrow as pa  # noqa: PLC0415 - lazy optional import
            import pyarrow.parquet as pq  # noqa: PLC0415 - lazy optional import
        except ImportError as exc:  # pragma: no cover - exercised without the extra
            raise ParquetUnavailableError(
                f"parquet export needs the optional extra: pip install '{PARQUET_EXTRA}'"
            ) from exc
        if not self.exists:
            return 0
        where = " WHERE session_id = ?" if session_id is not None else ""
        params = [session_id] if session_id is not None else []
        connection = self._connect()
        try:
            cursor = connection.execute(
                "SELECT seq, session_id, tool_name, outcome, project, producer_kind, "
                f"started_at, record FROM records{where} ORDER BY seq",
                params,
            )
            rows = [
                {
                    "seq": row[0],
                    "session_id": row[1],
                    "tool_name": row[2],
                    "outcome": row[3],
                    "project": row[4],
                    "producer_kind": row[5],
                    "started_at": row[6],
                    "record": row[7],
                }
                for row in cursor
            ]
        finally:
            connection.close()
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, destination)  # type: ignore[no-untyped-call]
        return len(rows)


def _row(seq: int, record: AgentRecord) -> dict[str, Any]:
    data = record.to_dict()
    return {
        "seq": seq,
        "session_id": record.session_id,
        "tool_name": record.tool.name,
        "outcome": record.outcome.value,
        "project": record.project,
        "producer_kind": effective_producer(record).kind.value,
        "started_at": data["started_at"],
        "record": _canonical(data),
    }


__all__ = [
    "INDEX_FILENAME",
    "INDEX_FORMAT_VERSION",
    "PARQUET_EXTRA",
    "IndexStatus",
    "ParquetUnavailableError",
    "QueryIndex",
    "index_path_for_store",
]
