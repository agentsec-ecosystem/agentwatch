"""Legal holds suspend retention/purge, with recorded provenance (M29 HLD-1, #450).

PRD 56 §HLD-1, design [legal-hold](../../../../docs/design/legal-hold.md).
Retention windows (AAT §9 12mo) and right-to-erasure collide with litigation
holds; a hold that lives only as a convention is invisible to an auditor and a
mistaken purge is irreversible.

A **hold** is a metadata-only append to the hash chain that names a scope and a
reason: ``session`` / ``project`` / ``time`` / ``principal``. While it is active:

* ``retention apply`` **skips** held records (they are listed with their hold IDs
  under ``--dry-run``);
* ``purge`` **fails closed** with the hold reference, and the refusal is itself a
  chain record; an explicit override requires a stated reason and is recorded as
  ``purge-override`` (conspicuous in evidence and the compliance report).

D-K is preserved: a hold prevents the tombstone from being written in the first
place; agentwatch never hard-deletes. Propagation to every derived index/export
is 30.EXT-5 (M30, behind the embedded index LUI-2) and is **not** in this branch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
    _parse_iso,
)
from agentwatch.store import MARKER_PRODUCER, RecordStore

HOLD_TOOL = "legal-hold"


class HoldKind(str, Enum):
    """What a hold's scope selects."""

    SESSION = "session"
    PROJECT = "project"
    TIME = "time"
    PRINCIPAL = "principal"


@dataclass(frozen=True)
class HoldScope:
    """A hold's scope: one session, project, principal, or a time window."""

    kind: HoldKind
    value: str | None = None
    start: datetime | None = None
    end: datetime | None = None

    def label(self) -> str:
        if self.kind is HoldKind.TIME:
            start = self.start.isoformat() if self.start else "-"
            end = self.end.isoformat() if self.end else "-"
            return f"time:{start}..{end}"
        return f"{self.kind.value}:{self.value or ''}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "value": self.value,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HoldScope:
        return cls(
            kind=HoldKind(str(data["kind"])),
            value=data.get("value"),
            start=_parse_iso(str(data["start"])) if data.get("start") else None,
            end=_parse_iso(str(data["end"])) if data.get("end") else None,
        )


def parse_scope(text: str) -> HoldScope:
    """Parse ``session:<id>`` / ``project:<path>`` / ``principal:<id>`` / ``time:<a>..<b>``."""
    kind, sep, value = text.partition(":")
    value = value.strip()
    if not sep or not kind or not value:
        raise ValueError(f"invalid hold scope {text!r}; expected KIND:VALUE")
    if kind == HoldKind.SESSION.value:
        return HoldScope(HoldKind.SESSION, value=value)
    if kind == HoldKind.PROJECT.value:
        return HoldScope(HoldKind.PROJECT, value=value)
    if kind == HoldKind.PRINCIPAL.value:
        return HoldScope(HoldKind.PRINCIPAL, value=value)
    if kind == HoldKind.TIME.value:
        left, sep2, right = value.partition("..")
        if not sep2 or not left.strip() or not right.strip():
            raise ValueError(
                f"invalid time hold scope {text!r}; expected time:<start>..<end>"
            )
        try:
            start = _parse_iso(left.strip())
            end = _parse_iso(right.strip())
        except ValueError:
            raise ValueError(
                f"invalid time hold scope {text!r}; expected ISO-8601 timestamps"
            ) from None
        if end < start:
            raise ValueError(f"invalid time hold scope {text!r}; end is before start")
        return HoldScope(HoldKind.TIME, start=start, end=end)
    raise ValueError(
        f"invalid hold scope {text!r}; expected one of session, project, time, principal"
    )


@dataclass(frozen=True)
class Hold:
    """An active hold read back from the chain."""

    hold_id: str
    scope: HoldScope
    reason: str
    ref: str | None
    added_at: datetime
    seq: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "hold_id": self.hold_id,
            "scope": self.scope.label(),
            "reason": self.reason,
            "ref": self.ref,
            "added_at": self.added_at.isoformat(),
            "seq": self.seq,
        }


@dataclass(frozen=True)
class HoldMarker:
    """One recorded hold event (add/release/blocked/override), for reports."""

    seq: int
    action: str
    hold_id: str
    hold_ids: tuple[str, ...]
    scope: str | None
    reason: str
    ref: str | None
    at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "action": self.action,
            "hold_id": self.hold_id,
            "hold_ids": list(self.hold_ids),
            "scope": self.scope,
            "reason": self.reason,
            "ref": self.ref,
            "at": self.at.isoformat(),
        }


@dataclass(frozen=True)
class HeldSkip:
    """A record that retention skipped because a hold protects it."""

    session_id: str
    seq: int
    started_at: datetime
    hold_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "seq": self.seq,
            "started_at": self.started_at.isoformat(),
            "hold_ids": list(self.hold_ids),
        }


def _hold_marker(
    action: str,
    arguments: dict[str, Any],
    moment: datetime,
    *,
    session_id: str = "agentwatch",
    outcome: Outcome = Outcome.OK,
) -> AgentRecord:
    return AgentRecord(
        session_id=session_id,
        agent=AgentIdentity(identity="agentwatch"),
        tool=ToolCall(
            name=HOLD_TOOL,
            arguments={"action": action, **arguments},
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
        outcome=outcome,
        started_at=moment,
        producer=MARKER_PRODUCER,
    )


def record_hold_add(
    store: RecordStore,
    scope: HoldScope,
    *,
    reason: str,
    ref: str | None = None,
    now: datetime | None = None,
) -> Hold:
    """Append a hold; the hold ID is derived from its chain position (``H<seq>``)."""
    moment = now or datetime.now(timezone.utc)
    entry = store.append(
        _hold_marker(
            "add",
            {"scope": scope.to_dict(), "reason": reason, "ref": ref},
            moment,
        )
    )
    return Hold(
        hold_id=f"H{entry.seq}",
        scope=scope,
        reason=reason,
        ref=ref,
        added_at=moment,
        seq=entry.seq,
    )


def record_hold_release(
    store: RecordStore,
    hold_id: str,
    *,
    reason: str | None = None,
    now: datetime | None = None,
) -> str | None:
    """Release an active hold; ``None`` when no such hold is active."""
    if hold_id not in {hold.hold_id for hold in active_holds(store)}:
        return None
    moment = now or datetime.now(timezone.utc)
    store.append(_hold_marker("release", {"hold_id": hold_id, "reason": reason}, moment))
    return hold_id


def record_purge_blocked(
    store: RecordStore,
    session_id: str,
    hold_id: str,
    *,
    now: datetime | None = None,
) -> None:
    """Record a purge refused by an active hold (never silent)."""
    moment = now or datetime.now(timezone.utc)
    store.append(
        _hold_marker(
            "purge-blocked",
            {"session_id": session_id, "hold_id": hold_id},
            moment,
            session_id=session_id,
            outcome=Outcome.DENIED,
        )
    )


def record_purge_override(
    store: RecordStore,
    session_id: str,
    *,
    reason: str,
    hold_ids: tuple[str, ...],
    now: datetime | None = None,
) -> None:
    """Record the explicit override that let a held purge proceed."""
    moment = now or datetime.now(timezone.utc)
    store.append(
        _hold_marker(
            "purge-override",
            {"session_id": session_id, "reason": reason, "hold_ids": list(hold_ids)},
            moment,
            session_id=session_id,
        )
    )


def active_holds(store: RecordStore) -> list[Hold]:
    """Every hold that has been added and not released, in chain order."""
    holds: dict[str, Hold] = {}
    for entry in store.entries():
        record = entry.record
        if record is None or record.tool.name != HOLD_TOOL:
            continue
        arguments = record.tool.arguments or {}
        action = arguments.get("action")
        if action == "add":
            scope = arguments.get("scope")
            if not isinstance(scope, dict):
                continue
            holds[f"H{entry.seq}"] = Hold(
                hold_id=f"H{entry.seq}",
                scope=HoldScope.from_dict(scope),
                reason=str(arguments.get("reason", "")),
                ref=arguments.get("ref"),
                added_at=record.started_at,
                seq=entry.seq,
            )
        elif action == "release":
            holds.pop(str(arguments.get("hold_id", "")), None)
    return list(holds.values())


def hold_records(store: RecordStore) -> list[HoldMarker]:
    """Every recorded hold event, in chain order (add/release/blocked/override)."""
    markers: list[HoldMarker] = []
    for entry in store.entries():
        record = entry.record
        if record is None or record.tool.name != HOLD_TOOL:
            continue
        arguments = record.tool.arguments or {}
        action = str(arguments.get("action", ""))
        raw_ids = arguments.get("hold_ids")
        hold_ids = tuple(str(value) for value in raw_ids) if isinstance(raw_ids, list) else ()
        scope = arguments.get("scope")
        scope_label = HoldScope.from_dict(scope).label() if isinstance(scope, dict) else None
        if action == "add":
            hold_id = f"H{entry.seq}"
        elif action in {"release", "purge-blocked"}:
            hold_id = str(arguments.get("hold_id", ""))
        else:
            hold_id = hold_ids[0] if hold_ids else ""
        markers.append(
            HoldMarker(
                seq=entry.seq,
                action=action,
                hold_id=hold_id,
                hold_ids=hold_ids,
                scope=scope_label,
                reason=str(arguments.get("reason", "") or ""),
                ref=arguments.get("ref"),
                at=record.started_at,
            )
        )
    return markers


def record_matches_hold(record: AgentRecord, hold: Hold) -> bool:
    """Whether one record falls inside a hold's scope."""
    scope = hold.scope
    if scope.kind is HoldKind.SESSION:
        return record.session_id == scope.value
    if scope.kind is HoldKind.PROJECT:
        return record.project == scope.value
    if scope.kind is HoldKind.PRINCIPAL:
        principals = {record.agent.principal, record.agent.identity}
        principals.update(record.agent.delegation_chain or ())
        return bool(scope.value) and scope.value in principals
    if scope.kind is HoldKind.TIME:
        if scope.start is not None and record.started_at < scope.start:
            return False
        return not (scope.end is not None and record.started_at > scope.end)
    return False


def held_hold_ids(record: AgentRecord, holds: list[Hold]) -> tuple[str, ...]:
    """The IDs of every hold that protects ``record``."""
    return tuple(hold.hold_id for hold in holds if record_matches_hold(record, hold))


def record_is_held(record: AgentRecord, holds: list[Hold]) -> bool:
    """Whether any active hold protects ``record``."""
    return any(record_matches_hold(record, hold) for hold in holds)


def held_skips(
    store: RecordStore, cutoff: datetime, *, holds: list[Hold] | None = None
) -> list[HeldSkip]:
    """Records older than ``cutoff`` that an active hold protects (for ``--dry-run``)."""
    active = active_holds(store) if holds is None else holds
    skips: list[HeldSkip] = []
    for entry in store.entries():
        record = entry.record
        if record is None or record.started_at >= cutoff:
            continue
        hold_ids = held_hold_ids(record, active)
        if hold_ids:
            skips.append(HeldSkip(record.session_id, entry.seq, record.started_at, hold_ids))
    return skips


def render_holds(holds: list[Hold]) -> str:
    """Render active holds as a tab-separated table."""
    lines = [f"agentwatch hold list: {len(holds)} active hold(s)"]
    if not holds:
        return "\n".join(lines)
    lines.append("HOLD\tSCOPE\tREF\tREASON\tADDED")
    for hold in holds:
        lines.append(
            f"{hold.hold_id}\t{hold.scope.label()}\t{hold.ref or '-'}\t{hold.reason}\t"
            f"{hold.added_at.isoformat()}"
        )
    return "\n".join(lines)


__all__ = [
    "HOLD_TOOL",
    "HeldSkip",
    "Hold",
    "HoldKind",
    "HoldMarker",
    "HoldScope",
    "active_holds",
    "held_hold_ids",
    "held_skips",
    "hold_records",
    "parse_scope",
    "record_hold_add",
    "record_hold_release",
    "record_is_held",
    "record_matches_hold",
    "record_purge_blocked",
    "record_purge_override",
    "render_holds",
]