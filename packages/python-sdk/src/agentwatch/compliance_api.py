"""Claude Compliance API ingest (M27 CCA-1, PRD 45).

Anthropic's Compliance API ``/v1/compliance/*`` returns organization activity as
JSON events: an **activity id + type**, an RFC-3339 timestamp, the organization,
**actor information** (type, email, user id), and event-specific fields. This
module maps such an export to records with authoritative attribution — the actor
email becomes a **hashed** on-behalf-of principal (IDN-1).

It is **consent-first**: the CLI refuses to pull or ingest without ``--consent``,
records the pull as a metadata-only ``store-access`` record, and never stores a
credential. A feed-vs-hook mismatch is surfaced as a classified
``compliance-discrepancy`` observation (metadata-only), **never silently merged**.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from agentwatch.identity import apply_identity_privacy
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    Producer,
    ProducerKind,
    RecordPrivacyMode,
    SecurityEvent,
    SecurityEventType,
    StepType,
    ToolCall,
    _parse_iso,
)
from agentwatch.redact import PrivacyMode, RedactionConfig
from agentwatch.secrets import redact_mapping
from agentwatch.store import MARKER_PRODUCER, RecordStore

HARNESS_ID = "claude-compliance"
COMPLIANCE_PRODUCER = Producer(kind=ProducerKind.IMPORT, name=HARNESS_ID)
DISCREPANCY_TOOL = "compliance-discrepancy"

_ERROR = frozenset({"error", "failed", "denied", "blocked"})
_PRIVACY_MAP = {
    PrivacyMode.METADATA_ONLY: RecordPrivacyMode.METADATA_ONLY,
    PrivacyMode.TRUNCATED: RecordPrivacyMode.TRUNCATED,
    PrivacyMode.HASHED: RecordPrivacyMode.HASHED,
    PrivacyMode.FULL: RecordPrivacyMode.FULL,
}


class ComplianceApiError(ValueError):
    """Raised when a compliance export cannot be read."""


@dataclass(frozen=True)
class ComplianceRead:
    """Outcome of reading a compliance export (skips reported, never silent)."""

    records: list[AgentRecord]
    skipped: int = 0


def _time(event: Mapping[str, Any]) -> datetime:
    for key in ("created_at", "created", "timestamp", "event_time"):
        raw = event.get(key)
        if isinstance(raw, str):
            try:
                return _parse_iso(raw)
            except ValueError:
                continue
    return datetime.now(timezone.utc)


def _events(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        for key in ("data", "events", "activity", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, Mapping)]
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    return []


def _capture(raw: Any, cfg: RedactionConfig | None) -> tuple[dict[str, Any] | None, Any]:
    if not isinstance(raw, Mapping):
        return None, None
    if cfg is None or cfg.mode is PrivacyMode.METADATA_ONLY or not cfg.capture_tool_args:
        return None, None
    return cast("dict[str, Any]", _redact(raw, cfg)), _PRIVACY_MAP[cfg.mode]


def _redact(value: Any, cfg: RedactionConfig) -> Any:
    if isinstance(value, str):
        return cfg.apply(value, allowed=True)
    if isinstance(value, Mapping):
        return {key: _redact(item, cfg) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, cfg) for item in value]
    return value


def _principal(actor: Any) -> AgentIdentity:
    identity = AgentIdentity(identity=HARNESS_ID)
    if isinstance(actor, Mapping):
        email = actor.get("email")
        if isinstance(email, str) and email:
            return apply_identity_privacy(
                AgentIdentity(identity=HARNESS_ID, principal=email),
                mode=RecordPrivacyMode.METADATA_ONLY,
            )
        user_id = actor.get("user_id")
        if isinstance(user_id, str) and user_id:
            identity = AgentIdentity(identity=HARNESS_ID, name=user_id)
    return identity


def read_compliance_export(
    path: Path | str, *, redaction: RedactionConfig | None = None
) -> ComplianceRead:
    """Read a Compliance API JSON export into records (read-only, fail-soft)."""
    export = Path(path)
    if not export.is_file():
        raise ComplianceApiError(f"no such compliance export: {export}")
    try:
        payload = json.loads(export.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ComplianceApiError(f"unreadable compliance export: {exc}") from exc

    records: list[AgentRecord] = []
    skipped = 0
    for event in _events(payload):
        event_type = event.get("type") or event.get("activity_type")
        if not isinstance(event_type, str) or not event_type:
            skipped += 1
            continue
        at = _time(event)
        session = event.get("session_id") or event.get("entity_id") or event.get("organization_id")
        session_id = str(session) if isinstance(session, str) and session else HARNESS_ID
        tool = event.get("tool_name") or event_type
        status = event.get("outcome") or event.get("status")
        failure = isinstance(status, str) and status.lower() in _ERROR
        outcome = Outcome.ERROR if failure else Outcome.OK

        details = {
            key: event[key]
            for key in ("actor", "organization_id", "ip_address", "user_agent", "resource")
            if key in event
        }
        masked, kinds = redact_mapping(details)
        captured, privacy = _capture(masked, redaction)
        security_event = (
            SecurityEvent(
                type=SecurityEventType.SECRET_DETECTED,
                emitted_at=at,
                emitter="agentwatch",
                tool=str(tool),
                evidence={"kinds": list(kinds)},
            )
            if kinds
            else None
        )
        tool_kwargs: dict[str, Any] = {"name": str(tool)}
        if captured is not None:
            tool_kwargs["arguments"] = captured
            tool_kwargs["privacy_mode"] = privacy
        records.append(
            AgentRecord(
                session_id=session_id,
                agent=_principal(event.get("actor")),
                tool=ToolCall(**tool_kwargs),
                outcome=outcome,
                started_at=at,
                harness=HARNESS_ID,
                producer=COMPLIANCE_PRODUCER,
                trace_id=session_id,
                span_id=str(event["id"]) if isinstance(event.get("id"), str) else None,
                step_type=StepType.OBSERVE,
                security_event=security_event,
            )
        )
    return ComplianceRead(records=records, skipped=skipped)


def classify_discrepancies(
    feed: list[AgentRecord], store: RecordStore
) -> tuple[list[AgentRecord], list[str]]:
    """Feed-vs-store mismatches as classified observations (never auto-merged)."""
    hook: dict[tuple[str, str], Outcome] = {}
    for record in store.records():
        if record.producer is not None and record.producer.name == HARNESS_ID:
            continue
        if record.span_id is None:
            continue
        hook[(record.session_id, record.span_id)] = record.outcome

    observations: list[AgentRecord] = []
    notes: list[str] = []
    for record in feed:
        if record.span_id is None:
            continue
        key = (record.session_id, record.span_id)
        stored = hook.get(key)
        if stored is None:
            continue
        if stored != record.outcome:
            note = f"{key[0]}/{key[1]}: hook={stored.value} feed={record.outcome.value}"
            notes.append(note)
            observations.append(
                AgentRecord(
                    session_id=record.session_id,
                    agent=AgentIdentity(identity="agentwatch"),
                    tool=ToolCall(
                        name=DISCREPANCY_TOOL,
                        arguments={"session_id": key[0], "span_id": key[1]},
                        privacy_mode=RecordPrivacyMode.METADATA_ONLY,
                    ),
                    outcome=Outcome.OK,
                    started_at=record.started_at,
                    producer=MARKER_PRODUCER,
                    step_type=StepType.OBSERVE,
                )
            )
    return observations, notes


__all__ = [
    "COMPLIANCE_PRODUCER",
    "DISCREPANCY_TOOL",
    "HARNESS_ID",
    "ComplianceApiError",
    "ComplianceRead",
    "classify_discrepancies",
    "read_compliance_export",
]
