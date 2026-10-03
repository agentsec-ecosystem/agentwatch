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
    response: dict[str, Any] | None = None
    privacy_mode: RecordPrivacyMode | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"name": self.name}
        if self.server is not None:
            data["server"] = self.server
        if self.arguments is not None:
            data["arguments"] = self.arguments
        if self.response is not None:
            data["response"] = self.response
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
            response=data.get("response"),
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


# ---------------------------------------------------------------------------
# Validation (M2 2.3/2.4): strict structural checks, reject-never-coerce (F8)
# ---------------------------------------------------------------------------


class RecordValidationError(ValueError):
    """Raised when a record or security event violates the normative schema."""


_RECORD_FIELDS = frozenset(
    {
        "schema_version",
        "session_id",
        "trace_id",
        "span_id",
        "parent_span_id",
        "harness",
        "agent",
        "tool",
        "outcome",
        "started_at",
        "ended_at",
        "duration_ms",
        "tokens",
        "cost_usd",
        "step_type",
        "security_event",
    }
)
_AGENT_FIELDS = frozenset(
    {
        "identity",
        "name",
        "version",
        "prompt_version",
        "model_version",
        "tool_schema_version",
        "workload_type",
    }
)
_TOOL_FIELDS = frozenset({"name", "server", "arguments", "response", "privacy_mode"})
_EVENT_FIELDS = frozenset(
    {
        "event_version",
        "type",
        "emitted_at",
        "emitter",
        "reason",
        "policy_id",
        "tool",
        "credential_ref",
        "evidence",
    }
)


def _fail(message: str) -> None:
    raise RecordValidationError(message)


def _require_table(data: Any, where: str) -> None:
    if not isinstance(data, dict):
        _fail(f"{where}: must be an object")


def _reject_unknown(data: dict[str, Any], allowed: frozenset[str], where: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        _fail(f"{where}: unknown key(s): {', '.join(unknown)}")


def _require(data: dict[str, Any], key: str, where: str) -> None:
    if key not in data:
        _fail(f"{where}: missing required field {key!r}")


def _check_str(value: Any, where: str, key: str, *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, str):
        _fail(f"{where}: {key} must be a string")


def _check_table(value: Any, where: str, key: str, *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, dict):
        _fail(f"{where}: {key} must be an object")


def _check_number(value: Any, where: str, key: str, *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{where}: {key} must be a number")


def _check_int(value: Any, where: str, key: str, *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"{where}: {key} must be an integer")


def _check_datetime(value: Any, where: str, key: str, *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, str):
        _fail(f"{where}: {key} must be a date-time string")
    try:
        _parse_iso(value)
    except ValueError:
        _fail(f"{where}: {key} is not a valid ISO-8601 date-time")


def _check_enum(
    value: Any, where: str, key: str, enum_cls: type[Enum], *, nullable: bool = False
) -> None:
    if value is None and nullable:
        return
    allowed = {member.value for member in enum_cls}
    if not isinstance(value, str) or value not in allowed:
        options = ", ".join(sorted(str(v) for v in allowed))
        _fail(f"{where}: {key} must be one of [{options}]")


def _validate_identity_dict(data: Any) -> None:
    _require_table(data, "agent")
    _reject_unknown(data, _AGENT_FIELDS, "agent")
    _require(data, "identity", "agent")
    _check_str(data["identity"], "agent", "identity")
    for key in _AGENT_FIELDS - {"identity"}:
        if key in data:
            _check_str(data[key], "agent", key, nullable=True)


def _validate_tool_dict(data: Any) -> None:
    _require_table(data, "tool")
    _reject_unknown(data, _TOOL_FIELDS, "tool")
    _require(data, "name", "tool")
    _check_str(data["name"], "tool", "name")
    if "server" in data:
        _check_str(data["server"], "tool", "server", nullable=True)
    if "arguments" in data:
        _check_table(data["arguments"], "tool", "arguments", nullable=True)
    if "response" in data:
        _check_table(data["response"], "tool", "response", nullable=True)
    if "privacy_mode" in data:
        _check_enum(data["privacy_mode"], "tool", "privacy_mode", RecordPrivacyMode, nullable=True)


def _validate_event_dict(data: Any) -> None:
    where = "security event"
    _require_table(data, where)
    _reject_unknown(data, _EVENT_FIELDS, where)
    for key in ("event_version", "type", "emitted_at"):
        _require(data, key, where)
    if data["event_version"] != EVENT_VERSION:
        _fail(
            f"{where}: unknown event_version {data['event_version']!r}; "
            f"expected {EVENT_VERSION!r}"
        )
    _check_enum(data["type"], where, "type", SecurityEventType)
    _check_datetime(data["emitted_at"], where, "emitted_at")
    for key in ("emitter", "reason", "policy_id", "tool", "credential_ref"):
        if key in data:
            _check_str(data[key], where, key, nullable=True)
    if "evidence" in data:
        _check_table(data["evidence"], where, "evidence", nullable=True)


def _validate_record_dict(data: Any) -> None:
    where = "record"
    _require_table(data, where)
    _reject_unknown(data, _RECORD_FIELDS, where)
    for key in ("schema_version", "session_id", "agent", "tool", "outcome", "started_at"):
        _require(data, key, where)
    if data["schema_version"] != SCHEMA_VERSION:
        _fail(
            f"{where}: unknown schema_version {data['schema_version']!r}; "
            f"expected {SCHEMA_VERSION!r}"
        )
    _check_str(data["session_id"], where, "session_id")
    for key in ("trace_id", "span_id", "parent_span_id", "harness"):
        if key in data:
            _check_str(data[key], where, key, nullable=True)
    _validate_identity_dict(data["agent"])
    _validate_tool_dict(data["tool"])
    _check_enum(data["outcome"], where, "outcome", Outcome)
    _check_datetime(data["started_at"], where, "started_at")
    if "ended_at" in data:
        _check_datetime(data["ended_at"], where, "ended_at", nullable=True)
    if "duration_ms" in data:
        _check_number(data["duration_ms"], where, "duration_ms", nullable=True)
    if "cost_usd" in data:
        _check_number(data["cost_usd"], where, "cost_usd", nullable=True)
    if "tokens" in data:
        _check_int(data["tokens"], where, "tokens", nullable=True)
    if "step_type" in data:
        _check_enum(data["step_type"], where, "step_type", StepType, nullable=True)
    if data.get("security_event") is not None:
        _validate_event_dict(data["security_event"])


def validate_record(data: Any) -> AgentRecord:
    """Validate a raw record mapping and return the model, or raise.

    Strict structural validation: unknown keys, missing required fields, wrong
    types, and bad enumerations are **rejected, never coerced** (F8). The input
    mapping is not mutated.
    """
    _validate_record_dict(data)
    try:
        return AgentRecord.from_dict(data)
    except (KeyError, TypeError, ValueError) as exc:  # pragma: no cover - guarded above
        raise RecordValidationError(f"record: {exc}") from exc


def validate_event(data: Any) -> SecurityEvent:
    """Validate a raw security-event mapping and return the model, or raise."""
    _validate_event_dict(data)
    try:
        return SecurityEvent.from_dict(data)
    except (KeyError, TypeError, ValueError) as exc:  # pragma: no cover - guarded above
        raise RecordValidationError(f"security event: {exc}") from exc
