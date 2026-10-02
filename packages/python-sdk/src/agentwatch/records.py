"""The agentwatch record and security-event model (M2).

This is the Python form of the normative contract published in ``schema/``:
``agent-record.schema.json`` and ``security-event.schema.json``. Records are
immutable, round-trip losslessly to JSON, and are the vocabulary every service
(analytics, API, store, export) consumes.

Validation lives in :func:`validate_record` / :func:`validate_event`; these
dataclasses are only the data shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# Versions mirror the `const` values in the published JSON schemas.
SCHEMA_VERSION = "0.1.0"
EVENT_VERSION = "0.1.0"


class Outcome(str, Enum):
    """Whether a tool call succeeded, failed, or was denied."""

    OK = "ok"
    ERROR = "error"
    DENIED = "denied"


class StepType(str, Enum):
    """The agent-behavior class of a record."""

    REASON = "reason"
    ACT = "act"
    OBSERVE = "observe"
    VERIFY = "verify"


class RecordPrivacyMode(str, Enum):
    """The privacy mode recorded on the wire (hyphenated, unlike SDK ``PrivacyMode``)."""

    METADATA_ONLY = "metadata-only"
    TRUNCATED = "truncated"
    HASHED = "hashed"
    FULL = "full"


class SecurityEventType(str, Enum):
    """The named, versioned agent-security event vocabulary."""

    DENIED = "denied"
    POLICY_FIRED = "policy-fired"
    SECRET_DETECTED = "secret-detected"
    REVOKED = "revoked"
    HALTED = "halted"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _iso(value: datetime) -> str:
    """Serialize an aware datetime to UTC ISO-8601 with an explicit offset."""
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 string to an aware UTC datetime (accepts trailing Z)."""
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _drop_none(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentIdentity:
    """The agent's identity and correlation dimensions."""

    identity: str
    name: str | None = None
    version: str | None = None
    prompt_version: str | None = None
    model_version: str | None = None
    tool_schema_version: str | None = None
    workload_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(
            {
                "identity": self.identity,
                "name": self.name,
                "version": self.version,
                "prompt_version": self.prompt_version,
                "model_version": self.model_version,
                "tool_schema_version": self.tool_schema_version,
                "workload_type": self.workload_type,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentIdentity:
        return cls(
            identity=data["identity"],
            name=data.get("name"),
            version=data.get("version"),
            prompt_version=data.get("prompt_version"),
            model_version=data.get("model_version"),
            tool_schema_version=data.get("tool_schema_version"),
            workload_type=data.get("workload_type"),
        )


@dataclass(frozen=True)
class ToolCall:
    """A tool invocation; ``arguments`` are redacted per ``privacy_mode``."""

    name: str
    server: str | None = None
    arguments: dict[str, Any] | None = None
    privacy_mode: RecordPrivacyMode | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"name": self.name}
        if self.server is not None:
            data["server"] = self.server
        if self.arguments is not None:
            data["arguments"] = self.arguments
        if self.privacy_mode is not None:
            data["privacy_mode"] = self.privacy_mode.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCall:
        mode = data.get("privacy_mode")
        return cls(
            name=data["name"],
            server=data.get("server"),
            arguments=data.get("arguments"),
            privacy_mode=RecordPrivacyMode(mode) if mode is not None else None,
        )


@dataclass(frozen=True)
class SecurityEvent:
    """A named security event, attached to the record it concerns."""

    type: SecurityEventType
    emitted_at: datetime
    event_version: str = EVENT_VERSION
    emitter: str | None = None
    reason: str | None = None
    policy_id: str | None = None
    tool: str | None = None
    credential_ref: str | None = None
    evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_version": self.event_version,
            "type": self.type.value,
            "emitted_at": _iso(self.emitted_at),
            **_drop_none(
                {
                    "emitter": self.emitter,
                    "reason": self.reason,
                    "policy_id": self.policy_id,
                    "tool": self.tool,
                    "credential_ref": self.credential_ref,
                    "evidence": self.evidence,
                }
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SecurityEvent:
        return cls(
            type=SecurityEventType(data["type"]),
            emitted_at=_parse_iso(data["emitted_at"]),
            event_version=data.get("event_version", EVENT_VERSION),
            emitter=data.get("emitter"),
            reason=data.get("reason"),
            policy_id=data.get("policy_id"),
            tool=data.get("tool"),
            credential_ref=data.get("credential_ref"),
            evidence=data.get("evidence"),
        )


@dataclass(frozen=True)
class AgentRecord:
    """A normalized agent activity record (tool call / behavior step)."""

    session_id: str
    agent: AgentIdentity
    tool: ToolCall
    outcome: Outcome
    started_at: datetime
    schema_version: str = SCHEMA_VERSION
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    harness: str | None = None
    ended_at: datetime | None = None
    duration_ms: float | None = None
    tokens: int | None = None
    cost_usd: float | None = None
    step_type: StepType | None = None
    security_event: SecurityEvent | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "agent": self.agent.to_dict(),
            "tool": self.tool.to_dict(),
            "outcome": self.outcome.value,
            "started_at": _iso(self.started_at),
        }
        data.update(
            _drop_none(
                {
                    "trace_id": self.trace_id,
                    "span_id": self.span_id,
                    "parent_span_id": self.parent_span_id,
                    "harness": self.harness,
                }
            )
        )
        if self.ended_at is not None:
            data["ended_at"] = _iso(self.ended_at)
        data.update(
            _drop_none(
                {
                    "duration_ms": self.duration_ms,
                    "tokens": self.tokens,
                    "cost_usd": self.cost_usd,
                }
            )
        )
        if self.step_type is not None:
            data["step_type"] = self.step_type.value
        if self.security_event is not None:
            data["security_event"] = self.security_event.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentRecord:
        ended = data.get("ended_at")
        step = data.get("step_type")
        event = data.get("security_event")
        return cls(
            session_id=data["session_id"],
            agent=AgentIdentity.from_dict(data["agent"]),
            tool=ToolCall.from_dict(data["tool"]),
            outcome=Outcome(data["outcome"]),
            started_at=_parse_iso(data["started_at"]),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            trace_id=data.get("trace_id"),
            span_id=data.get("span_id"),
            parent_span_id=data.get("parent_span_id"),
            harness=data.get("harness"),
            ended_at=_parse_iso(ended) if ended is not None else None,
            duration_ms=data.get("duration_ms"),
            tokens=data.get("tokens"),
            cost_usd=data.get("cost_usd"),
            step_type=StepType(step) if step is not None else None,
            security_event=SecurityEvent.from_dict(event) if event is not None else None,
        )
