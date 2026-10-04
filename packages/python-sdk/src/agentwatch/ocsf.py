"""OCSF and CloudEvents mappings for the security-event schema (M20 S8, PRD 36).

Emitting a standard is **export, not becoming the standard's consumer** (PRD 14):
agentwatch is not a SIEM, but it speaks the two dialects a receiving side already
speaks. This module is a pure transcode — no ingestion, no network, no state.

* OCSF: every agentwatch event type maps to a documented OCSF class/category/
  activity. Agentwatch fields OCSF cannot express are preserved under
  ``unmapped`` (lossless-or-explicit); an event type without a mapping is still
  exported with an explicit ``unmapped`` marker, never dropped.
* CloudEvents: the open 1.0 envelope for the ``event emit`` path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from agentwatch.records import SecurityEvent

# Pinned OCSF version; output carries it in ``metadata.version`` and tests check
# against it so mapping drift is caught (PRD 36 S8 risk).
OCSF_VERSION = "1.5.0"
CLOUDEVENTS_VERSION = "1.0"
CLOUDEVENTS_SOURCE = "agentwatch"

# OCSF category uids/names used by the mapping.
_CATEGORY_FINDINGS = (2, "Findings")
_CATEGORY_IAM = (3, "Identity & Access Management")


@dataclass(frozen=True)
class OcsfTarget:
    """A documented OCSF target for one agentwatch event type."""

    class_uid: int
    class_name: str
    category_uid: int
    category_name: str
    activity_id: int
    activity_name: str


# Documented mapping table (agentwatch event type -> OCSF target). Published in
# docs/design/ocsf-mapping.md. Unknown types are exported as unmapped.
MAPPING_TABLE: dict[str, OcsfTarget] = {
    "denied": OcsfTarget(3003, "Authorize", *_CATEGORY_IAM, 2, "Deny"),
    "policy-fired": OcsfTarget(2004, "Detection Finding", *_CATEGORY_FINDINGS, 1, "Create"),
    "secret-detected": OcsfTarget(2006, "Data Security Finding", *_CATEGORY_FINDINGS, 1, "Create"),
    "revoked": OcsfTarget(3003, "Authorize", *_CATEGORY_IAM, 2, "Deny"),
    "halted": OcsfTarget(2004, "Detection Finding", *_CATEGORY_FINDINGS, 1, "Create"),
    "drift-detected": OcsfTarget(2004, "Detection Finding", *_CATEGORY_FINDINGS, 1, "Create"),
    "tool-surface-changed": OcsfTarget(2004, "Detection Finding", *_CATEGORY_FINDINGS, 1, "Create"),
}

# OCSF cannot express these native fields directly; they ride under `unmapped`.
_UNMAPPED_FIELDS = ("event_version", "emitter", "policy_id", "tool", "credential_ref", "evidence")


def ocsf_target(event_type: str) -> OcsfTarget | None:
    """The OCSF target for an event type, or ``None`` when unmapped."""
    return MAPPING_TABLE.get(event_type)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _ocsf_id(event: SecurityEvent, *, session_id: str | None) -> str:
    parts = [event.type.value, _iso(event.emitted_at), session_id or "", event.emitter or ""]
    return "|".join(parts)


def to_ocsf(
    event: SecurityEvent, *, session_id: str | None = None, seq: int | None = None
) -> dict[str, Any]:
    """Transcode one security event to an OCSF object (lossless-or-explicit).

    Fields OCSF cannot express are preserved under ``unmapped``. A type with no
    mapping is still emitted, flagged ``unmapped: true`` — never dropped.
    """
    target = ocsf_target(event.type.value)
    unmapped: dict[str, Any] = {
        field: value
        for field in _UNMAPPED_FIELDS
        if (value := getattr(event, field, None)) is not None
    }
    if target is None:
        unmapped["event_type"] = event.type.value
    if session_id is not None:
        unmapped["session_id"] = session_id
    if seq is not None:
        unmapped["agentwatch_seq"] = seq

    record: dict[str, Any] = {
        "metadata": {"version": OCSF_VERSION, "product": {"name": "agentwatch"}},
        "time": _ocsf_time(event.emitted_at),
        "type_uid": (target.class_uid * 100 + target.activity_id) if target else 0,
        "unmapped": unmapped,
    }
    if target is not None:
        record.update(
            {
                "class_uid": target.class_uid,
                "class_name": target.class_name,
                "category_uid": target.category_uid,
                "category_name": target.category_name,
                "activity_id": target.activity_id,
                "activity_name": target.activity_name,
            }
        )
    else:
        record["unmapped_type"] = True
    if event.reason is not None:
        record["message"] = event.reason
    if event.tool is not None:
        record["unmapped"]["tool_name"] = event.tool
    return record


def _ocsf_time(value: datetime) -> int:
    """OCSF timestamps are Unix epoch milliseconds."""
    return int(value.timestamp() * 1000)


def to_cloudevents(
    event: SecurityEvent, *, session_id: str | None = None, seq: int | None = None
) -> dict[str, Any]:
    """Wrap one security event in a CloudEvents 1.0 JSON envelope."""
    envelope: dict[str, Any] = {
        "specversion": CLOUDEVENTS_VERSION,
        "id": _ocsf_id(event, session_id=session_id),
        "source": CLOUDEVENTS_SOURCE,
        "type": f"io.agentwatch.security-event.{event.type.value}",
        "time": _iso(event.emitted_at),
        "datacontenttype": "application/json",
        "data": event.to_dict(),
    }
    if session_id is not None:
        envelope["subject"] = session_id
    if seq is not None:
        envelope["agentwatchseq"] = seq
    return envelope


def session_ocsf(
    events: list[tuple[int, SecurityEvent]], *, session_id: str | None = None
) -> list[dict[str, Any]]:
    """OCSF objects for a session's ``(seq, event)`` pairs, in order."""
    return [
        to_ocsf(event, session_id=session_id, seq=seq) for seq, event in sorted(events, key=_seq)
    ]


def session_cloudevents(
    events: list[tuple[int, SecurityEvent]], *, session_id: str | None = None
) -> list[dict[str, Any]]:
    """CloudEvents envelopes for a session's ``(seq, event)`` pairs, in order."""
    return [
        to_cloudevents(event, session_id=session_id, seq=seq)
        for seq, event in sorted(events, key=_seq)
    ]


def _seq(item: tuple[int, SecurityEvent]) -> int:
    return item[0]


__all__ = [
    "CLOUDEVENTS_SOURCE",
    "CLOUDEVENTS_VERSION",
    "MAPPING_TABLE",
    "OCSF_VERSION",
    "OcsfTarget",
    "ocsf_target",
    "session_cloudevents",
    "session_ocsf",
    "to_cloudevents",
    "to_ocsf",
]
