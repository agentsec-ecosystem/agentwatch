"""Quarantine log and operator tooling for undecodable events (M5 B4, M16 S27).

Normalization failures must not drop the original bytes: they are preserved
verbatim here (owner-only) so the event can be diagnosed and, later, reprocessed.
The quarantine is evidence, not records — it is excluded from the store.

B4 shipped the queue; S27 adds the operator commands that were missing: list,
inspect (redacted by default, ``--raw`` gated and audited), requeue through the
current adapter, and an explicit clear. Entries carry a stable short id so a
dead-letter queue is no longer an append-only pile with no handles.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentwatch.records import AgentRecord
from agentwatch.secrets import redact_secrets
from agentwatch.store import RecordStore
from agentwatch.store_access import DestinationKind, record_store_access

Normalizer = Callable[[Mapping[str, Any]], list[AgentRecord]]


class QuarantineError(ValueError):
    """Raised when an operator command cannot proceed safely (fail-closed)."""


@dataclass(frozen=True)
class QuarantineEntry:
    """One quarantined frame, with a stable id."""

    id: str
    index: int
    at: datetime | None
    reason: str
    raw: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        """A payload-free view (reason + arrival time + id)."""
        return {
            "id": self.id,
            "reason": self.reason,
            "at": self.at.isoformat() if self.at else None,
        }


@dataclass(frozen=True)
class InspectReport:
    """The result of inspecting one entry."""

    entry: QuarantineEntry
    payload: str
    raw: bool
    masked_kinds: tuple[str, ...]


@dataclass(frozen=True)
class RequeueReport:
    """Outcome of a requeue pass."""

    requeued: int
    records: int
    still_failing: int
    remaining: int


def _entry_id(raw: str, at: str) -> str:
    return hashlib.sha256((at + "\x00" + raw).encode("utf-8", errors="replace")).hexdigest()[:12]


def _parse_at(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class QuarantineLog:
    """Append-only, owner-only log of raw frames that failed to normalize."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def add(self, raw: str | bytes, *, reason: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
        at = datetime.now(timezone.utc).isoformat()
        entry = {"id": _entry_id(text, at), "at": at, "reason": reason, "raw": text}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        os.chmod(self.path, 0o600)

    def entries(self) -> list[dict[str, Any]]:
        """Raw entry dictionaries, in log order (legacy entries get a derived id)."""
        if not self.path.exists():
            return []
        result: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            if "id" not in obj:
                obj["id"] = _entry_id(str(obj.get("raw", "")), str(obj.get("at", "")))
            result.append(obj)
        return result

    def records(self) -> list[QuarantineEntry]:
        """Typed entries, in log order."""
        result: list[QuarantineEntry] = []
        for index, obj in enumerate(self.entries()):
            arguments: dict[str, Any] = {}
            raw_arguments = obj.get("arguments")
            if isinstance(raw_arguments, dict):
                arguments = dict(raw_arguments)
            result.append(
                QuarantineEntry(
                    id=str(obj.get("id", "")),
                    index=index,
                    at=_parse_at(obj.get("at")),
                    reason=str(obj.get("reason", "")),
                    raw=str(obj.get("raw", "")),
                    arguments=arguments,
                )
            )
        return result

    def get(self, entry_id: str) -> QuarantineEntry | None:
        for entry in self.records():
            if entry.id == entry_id:
                return entry
        return None

    def size_bytes(self) -> int:
        return self.path.stat().st_size if self.path.exists() else 0

    def replace_entries(self, entries: Iterable[QuarantineEntry]) -> None:
        kept = list(entries)
        if not kept:
            self.path.unlink(missing_ok=True)
            return
        lines = [
            json.dumps(
                {
                    "id": e.id,
                    "at": e.at.isoformat() if e.at else None,
                    "reason": e.reason,
                    "raw": e.raw,
                },
                ensure_ascii=False,
            )
            for e in kept
        ]
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)
        os.chmod(self.path, 0o600)


def list_entries(quarantine: QuarantineLog) -> list[QuarantineEntry]:
    """Every quarantined entry, newest first (payload-free summaries)."""
    return list(reversed(quarantine.records()))


def inspect_entry(
    quarantine: QuarantineLog,
    store: RecordStore,
    entry_id: str,
    *,
    raw: bool = False,
    now: datetime | None = None,
) -> InspectReport:
    """Inspect one entry: redacted by default; ``raw`` is gated and audited.

    A raw read is recorded as a ``store-access`` record (S21) because it exposes
    the unredacted bytes the privacy posture otherwise keeps out of every read.
    """
    entry = quarantine.get(entry_id)
    if entry is None:
        raise QuarantineError(f"no quarantine entry with id {entry_id}")
    if not raw:
        masked, kinds = redact_secrets(entry.raw)
        return InspectReport(entry=entry, payload=masked, raw=False, masked_kinds=kinds)
    record_store_access(
        store,
        command="quarantine-inspect",
        records=1,
        destination_kind=DestinationKind.STDOUT,
        now=now,
    )
    return InspectReport(entry=entry, payload=entry.raw, raw=True, masked_kinds=())


def select_entries(
    quarantine: QuarantineLog, *, ids: Iterable[str] = (), all_entries: bool = False
) -> list[QuarantineEntry]:
    """Resolve the entries a requeue should attempt, or raise on a bad id."""
    records = quarantine.records()
    if all_entries or not ids:
        return records
    wanted = list(ids)
    selected: list[QuarantineEntry] = []
    for entry_id in wanted:
        entry = next((candidate for candidate in records if candidate.id == entry_id), None)
        if entry is None:
            raise QuarantineError(f"no quarantine entry with id {entry_id}")
        selected.append(entry)
    return selected


def requeue_entries(
    quarantine: QuarantineLog,
    store: RecordStore,
    *,
    normalizer: Normalizer,
    ids: Iterable[str] = (),
    all_entries: bool = False,
    now: datetime | None = None,
) -> RequeueReport:
    """Re-run selected entries through ``normalizer``; drop the ones that now work.

    A still-failing entry stays quarantined with its new reason (never silently
    dropped); a successful one moves its records into the store.
    """
    selected = select_entries(quarantine, ids=ids, all_entries=all_entries)
    selected_ids = {entry.id for entry in selected}
    requeued = 0
    records = 0
    still_failing = 0
    kept: list[QuarantineEntry] = []
    for entry in quarantine.records():
        if entry.id not in selected_ids:
            kept.append(entry)
            continue
        try:
            parsed: Any = json.loads(entry.raw)
        except json.JSONDecodeError:
            parsed = None
        if not isinstance(parsed, Mapping):
            still_failing += 1
            kept.append(_with_reason(entry, "requeue-error: not a JSON object"))
            continue
        try:
            normalized = normalizer(parsed)
        except (ValueError, TypeError, KeyError) as exc:
            still_failing += 1
            kept.append(_with_reason(entry, f"requeue-error: {exc}"))
            continue
        if not normalized:
            still_failing += 1
            kept.append(_with_reason(entry, "requeue-error: normalizer produced no records"))
            continue
        for record in normalized:
            store.append(record)
        requeued += 1
        records += len(normalized)
    quarantine.replace_entries(kept)
    return RequeueReport(
        requeued=requeued,
        records=records,
        still_failing=still_failing,
        remaining=len(kept),
    )


def _with_reason(entry: QuarantineEntry, reason: str) -> QuarantineEntry:
    return QuarantineEntry(
        id=entry.id,
        index=entry.index,
        at=entry.at,
        reason=reason,
        raw=entry.raw,
        arguments=entry.arguments,
    )


def clear_entries(quarantine: QuarantineLog, *, yes: bool) -> int:
    """Delete every quarantined entry. Requires ``yes`` when the queue is not empty."""
    count = len(quarantine.records())
    if count and not yes:
        raise QuarantineError("refusing to clear the quarantine without --yes")
    quarantine.replace_entries([])
    return count
