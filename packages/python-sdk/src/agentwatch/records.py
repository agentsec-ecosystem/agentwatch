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

# Versions mirror the version range declared in the published JSON schemas. The
# current version is what new records/events are emitted with; the supported
# tuple is the accepted read range. Additive minors keep old readers' data
# readable (W5); the emit-version flip to 0.2.0 lands with the v0.2.0 release
# (M30 30.3), not per-field.
SCHEMA_VERSION = "0.1.0"
SUPPORTED_SCHEMA_VERSIONS = ("0.1.0", "0.2.0")
EVENT_VERSION = "0.1.0"
SUPPORTED_EVENT_VERSIONS = ("0.1.0", "0.2.0")


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


class RecordPhase(str, Enum):
    """Whether a record describes a decision before or after execution (AAT-1).

    AAT requires pre-execution recording ("a denial logged only after execution
    provides no evidence it was enforced"). ``UNKNOWN`` is the honest default:
    it is used when the phase cannot be proven, and is never inferred from the
    ``outcome`` (S14 reject-never-coerce discipline).
    """

    PRE_EXECUTION = "pre_execution"
    POST_EXECUTION = "post_execution"
    UNKNOWN = "unknown"


class CredentialClass(str, Enum):
    """The class of credential the agent acted under (IDN-1, AAT identity).

    A classification, never a secret: it names *what kind* of credential was
    used, not its value.
    """

    API_KEY = "api-key"
    OAUTH = "oauth"
    SVID = "svid"
    AMBIENT_SHARED = "ambient/shared"


class RecordPrivacyMode(str, Enum):
    """The privacy mode recorded on the wire (hyphenated, unlike SDK ``PrivacyMode``)."""

    METADATA_ONLY = "metadata-only"
    TRUNCATED = "truncated"
    HASHED = "hashed"
    FULL = "full"


class ProducerKind(str, Enum):
    """How a record entered the store (provenance, M15 S26; demo M19 S31)."""

    HOOK = "hook"
    IMPORT = "import"
    EVENT = "event"
    INGEST = "ingest"
    PROXY = "proxy"
    SDK = "sdk"
    DEMO = "demo"


class Approval(str, Enum):
    """Who authorized a tool call (M19 S14).

    ``unknown`` is the honest default: it is persisted whenever the harness
    cannot *prove* whether a human approved, an allow-list auto-approved, or no
    permission was required. It is never guessed.
    """

    USER = "user"
    AUTO = "auto"
    NOT_REQUIRED = "not-required"
    DENIED = "denied"
    UNKNOWN = "unknown"


class AuthorizationSource(str, Enum):
    """Who or what authorized a tool call (M29 APV-1, taxonomy v2).

    ``unknown`` is the honest default and is **never** inferred from
    ``outcome=ok``: an allow-list rule, a model classifier, a bypassed mode and a
    human approval are distinct facts (PRD 49).
    """

    HUMAN_ONCE = "human-once"
    HUMAN_REMEMBERED = "human-remembered"
    RULE = "rule"
    CLASSIFIER = "classifier"
    HOOK = "hook"
    BYPASS = "bypass"
    NOT_REQUIRED = "not-required"
    DENIED = "denied"
    UNKNOWN = "unknown"


class AuthorizationDeny(str, Enum):
    """Who or what refused a call, when ``source=denied`` (M29 APV-1)."""

    HUMAN = "human"
    RULE = "rule"
    CLASSIFIER = "classifier"
    HOOK = "hook"
    UNKNOWN = "unknown"


class AuthorizationEvidence(str, Enum):
    """How the authorization source was established (M29 APV-1)."""

    HARNESS_NATIVE = "harness-native"
    INFERRED = "inferred"
    SESSION_MODE = "session-mode"


class PermissionMode(str, Enum):
    """The permission mode in force at the call (M29 APV-2)."""

    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    PLAN = "plan"
    AUTO = "auto"
    DONT_ASK = "dontAsk"
    BYPASS_PERMISSIONS = "bypassPermissions"
    UNKNOWN = "unknown"


class SecurityEventType(str, Enum):
    """The named, versioned agent-security event vocabulary."""

    DENIED = "denied"
    POLICY_FIRED = "policy-fired"
    SECRET_DETECTED = "secret-detected"
    REVOKED = "revoked"
    HALTED = "halted"
    # M11: a trailing-baseline deviation — an observation/signal, never enforcement.
    DRIFT_DETECTED = "drift-detected"
    # M20: the tool surface an MCP server presented changed between sessions — an
    # observation, never a malware verdict (PRD 36 S4, sixth event type via W5).
    TOOL_SURFACE_CHANGED = "tool-surface-changed"
    # v0.2.0: a cross-agent delegation was observed (A2A-2, PRD 45). An
    # observation of an on-behalf-of hop, never an authorization verdict.
    AGENT_DELEGATION = "agent-delegation"


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
class Producer:
    """The provenance of one record: how and by what it was produced (M15 S26)."""

    kind: ProducerKind
    name: str | None = None
    version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({"kind": self.kind.value, "name": self.name, "version": self.version})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Producer:
        return cls(
            kind=ProducerKind(data["kind"]),
            name=data.get("name"),
            version=data.get("version"),
        )


@dataclass(frozen=True)
class AgentIdentity:
    """The agent's identity and correlation dimensions.

    The v0.2.0 ``agent_identity`` dimension (IDN-1) is additive on this object:
    ``workload_identity`` (a SPIFFE/WIMSE URI when the harness exposes one),
    ``credential_class``, ``principal`` (hashed by default in metadata-only), and
    ``delegation_chain`` (the on-behalf-of chain, principals hashed by default).
    Identity fields never carry secret material.
    """

    identity: str
    name: str | None = None
    version: str | None = None
    prompt_version: str | None = None
    model_version: str | None = None
    tool_schema_version: str | None = None
    workload_type: str | None = None
    workload_identity: str | None = None
    credential_class: CredentialClass | None = None
    principal: str | None = None
    delegation_chain: tuple[str, ...] | None = None

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
                "workload_identity": self.workload_identity,
                "credential_class": (
                    self.credential_class.value if self.credential_class is not None else None
                ),
                "principal": self.principal,
                "delegation_chain": (
                    list(self.delegation_chain) if self.delegation_chain is not None else None
                ),
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentIdentity:
        credential_class = data.get("credential_class")
        delegation_chain = data.get("delegation_chain")
        return cls(
            identity=data["identity"],
            name=data.get("name"),
            version=data.get("version"),
            prompt_version=data.get("prompt_version"),
            model_version=data.get("model_version"),
            tool_schema_version=data.get("tool_schema_version"),
            workload_type=data.get("workload_type"),
            workload_identity=data.get("workload_identity"),
            credential_class=(
                CredentialClass(credential_class) if credential_class is not None else None
            ),
            principal=data.get("principal"),
            delegation_chain=(
                tuple(delegation_chain) if delegation_chain is not None else None
            ),
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
class Authorization:
    """The versioned authorization decision attached to a record (M29 APV-1).

    ``source`` names who/what allowed the call; ``deny`` is populated only when
    ``source`` is ``denied``; ``evidence`` records how confidently the source was
    established. Metadata only — never a judgement of correctness.
    """

    source: AuthorizationSource
    deny: AuthorizationDeny | None = None
    evidence: AuthorizationEvidence | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(
            {
                "source": self.source.value,
                "deny": self.deny.value if self.deny is not None else None,
                "evidence": self.evidence.value if self.evidence is not None else None,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Authorization:
        deny = data.get("deny")
        evidence = data.get("evidence")
        return cls(
            source=AuthorizationSource(data["source"]),
            deny=AuthorizationDeny(deny) if deny is not None else None,
            evidence=AuthorizationEvidence(evidence) if evidence is not None else None,
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
    traceparent: str | None = None
    harness: str | None = None
    project: str | None = None
    host: str | None = None
    parent_session_id: str | None = None
    producer: Producer | None = None
    ended_at: datetime | None = None
    duration_ms: float | None = None
    tokens: int | None = None
    cost_usd: float | None = None
    step_type: StepType | None = None
    record_phase: RecordPhase | None = None
    approval: Approval | None = None
    authorization: Authorization | None = None
    permission_mode: PermissionMode | None = None
    environment: dict[str, Any] | None = None
    truncated: dict[str, Any] | None = None
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
                    "traceparent": self.traceparent,
                    "harness": self.harness,
                    "project": self.project,
                    "host": self.host,
                    "parent_session_id": self.parent_session_id,
                }
            )
        )
        if self.producer is not None:
            data["producer"] = self.producer.to_dict()
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
        if self.record_phase is not None:
            data["record_phase"] = self.record_phase.value
        if self.approval is not None:
            data["approval"] = self.approval.value
        if self.authorization is not None:
            data["authorization"] = self.authorization.to_dict()
        if self.permission_mode is not None:
            data["permission_mode"] = self.permission_mode.value
        if self.environment is not None:
            data["environment"] = self.environment
        if self.truncated is not None:
            data["truncated"] = self.truncated
        if self.security_event is not None:
            data["security_event"] = self.security_event.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentRecord:
        ended = data.get("ended_at")
        step = data.get("step_type")
        phase = data.get("record_phase")
        approval = data.get("approval")
        authorization = data.get("authorization")
        permission_mode = data.get("permission_mode")
        event = data.get("security_event")
        producer = data.get("producer")
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
            traceparent=data.get("traceparent"),
            harness=data.get("harness"),
            project=data.get("project"),
            host=data.get("host"),
            parent_session_id=data.get("parent_session_id"),
            producer=Producer.from_dict(producer) if producer is not None else None,
            ended_at=_parse_iso(ended) if ended is not None else None,
            duration_ms=data.get("duration_ms"),
            tokens=data.get("tokens"),
            cost_usd=data.get("cost_usd"),
            step_type=StepType(step) if step is not None else None,
            record_phase=RecordPhase(phase) if phase is not None else None,
            approval=Approval(approval) if approval is not None else None,
            authorization=(
                Authorization.from_dict(authorization) if authorization is not None else None
            ),
            permission_mode=(
                PermissionMode(permission_mode) if permission_mode is not None else None
            ),
            environment=data.get("environment"),
            truncated=data.get("truncated"),
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
        "traceparent",
        "harness",
        "project",
        "host",
        "parent_session_id",
        "producer",
        "agent",
        "tool",
        "outcome",
        "started_at",
        "ended_at",
        "duration_ms",
        "tokens",
        "cost_usd",
        "step_type",
        "record_phase",
        "approval",
        "authorization",
        "permission_mode",
        "environment",
        "truncated",
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
        "workload_identity",
        "credential_class",
        "principal",
        "delegation_chain",
    }
)
_TOOL_FIELDS = frozenset({"name", "server", "arguments", "response", "privacy_mode"})
_PRODUCER_FIELDS = frozenset({"kind", "name", "version"})
_AUTHORIZATION_FIELDS = frozenset({"source", "deny", "evidence"})
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


def _check_str_list(value: Any, where: str, key: str, *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _fail(f"{where}: {key} must be an array of strings")


def _validate_identity_dict(data: Any) -> None:
    _require_table(data, "agent")
    _reject_unknown(data, _AGENT_FIELDS, "agent")
    _require(data, "identity", "agent")
    _check_str(data["identity"], "agent", "identity")
    for key in _AGENT_FIELDS - {"identity", "credential_class", "delegation_chain"}:
        if key in data:
            _check_str(data[key], "agent", key, nullable=True)
    if "credential_class" in data:
        _check_enum(
            data["credential_class"], "agent", "credential_class", CredentialClass, nullable=True
        )
    if "delegation_chain" in data:
        _check_str_list(data["delegation_chain"], "agent", "delegation_chain", nullable=True)


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


def _validate_producer_dict(data: Any) -> None:
    where = "producer"
    _require_table(data, where)
    _reject_unknown(data, _PRODUCER_FIELDS, where)
    _require(data, "kind", where)
    _check_enum(data["kind"], where, "kind", ProducerKind)
    for key in ("name", "version"):
        if key in data:
            _check_str(data[key], where, key, nullable=True)


def _validate_authorization_dict(data: Any) -> None:
    where = "authorization"
    _require_table(data, where)
    _reject_unknown(data, _AUTHORIZATION_FIELDS, where)
    _require(data, "source", where)
    _check_enum(data["source"], where, "source", AuthorizationSource)
    if "deny" in data:
        _check_enum(data["deny"], where, "deny", AuthorizationDeny, nullable=True)
    if "evidence" in data:
        _check_enum(data["evidence"], where, "evidence", AuthorizationEvidence, nullable=True)


def _validate_event_dict(data: Any) -> None:
    where = "security event"
    _require_table(data, where)
    _reject_unknown(data, _EVENT_FIELDS, where)
    for key in ("event_version", "type", "emitted_at"):
        _require(data, key, where)
    if data["event_version"] not in SUPPORTED_EVENT_VERSIONS:
        supported = ", ".join(repr(v) for v in SUPPORTED_EVENT_VERSIONS)
        _fail(
            f"{where}: unknown event_version {data['event_version']!r}; "
            f"supported: [{supported}]"
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
    if data["schema_version"] not in SUPPORTED_SCHEMA_VERSIONS:
        supported = ", ".join(repr(v) for v in SUPPORTED_SCHEMA_VERSIONS)
        _fail(
            f"{where}: unknown schema_version {data['schema_version']!r}; "
            f"supported: [{supported}]"
        )
    _check_str(data["session_id"], where, "session_id")
    for key in (
        "trace_id",
        "span_id",
        "parent_span_id",
        "traceparent",
        "harness",
        "project",
        "host",
        "parent_session_id",
    ):
        if key in data:
            _check_str(data[key], where, key, nullable=True)
    if data.get("producer") is not None:
        _validate_producer_dict(data["producer"])
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
    if "record_phase" in data:
        _check_enum(data["record_phase"], where, "record_phase", RecordPhase, nullable=True)
    if "approval" in data:
        _check_enum(data["approval"], where, "approval", Approval, nullable=True)
    if data.get("authorization") is not None:
        _validate_authorization_dict(data["authorization"])
    if "permission_mode" in data:
        _check_enum(
            data["permission_mode"], where, "permission_mode", PermissionMode, nullable=True
        )
    if "environment" in data:
        _check_table(data["environment"], where, "environment", nullable=True)
    if "truncated" in data:
        _check_table(data["truncated"], where, "truncated", nullable=True)
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


def effective_producer(record: AgentRecord) -> Producer:
    """The record's producer, inferring ``hook`` for legacy records (M15 S26).

    Records written before ``producer`` existed carry no field; they are read as
    an inferred ``hook`` producer whose ``name`` is the record's harness. The
    value is never written back silently (Q7).
    """
    if record.producer is not None:
        return record.producer
    return Producer(kind=ProducerKind.HOOK, name=record.harness)


def producer_is_inferred(record: AgentRecord) -> bool:
    """Whether :func:`effective_producer` had to infer a legacy producer."""
    return record.producer is None


def effective_approval(record: AgentRecord) -> Approval:
    """The record's authorization decision, reading legacy records as ``unknown``.

    Legacy records (before the field existed) are read as ``unknown`` — never
    inferred from ``outcome`` or the tool name (M19 S14, F8 reject-never-coerce).
    The value is never written back silently.
    """
    return record.approval if record.approval is not None else Approval.UNKNOWN


# Read-time mapping from the legacy S14 ``approval`` five-value field to the
# authorization v2 taxonomy (M29 APV-1). The stored legacy value is never
# rewritten; only the effective view maps it.
_LEGACY_APPROVAL_SOURCE = {
    Approval.USER: AuthorizationSource.HUMAN_ONCE,
    Approval.AUTO: AuthorizationSource.RULE,
    Approval.NOT_REQUIRED: AuthorizationSource.NOT_REQUIRED,
    Approval.DENIED: AuthorizationSource.DENIED,
    Approval.UNKNOWN: AuthorizationSource.UNKNOWN,
}


def effective_authorization(record: AgentRecord) -> Authorization:
    """The record's authorization decision, mapping legacy S14 at read time.

    When the v2 ``authorization`` object is absent the legacy ``approval`` value
    is translated (``user``→``human-once``, ``auto``→``rule``, ``denied``→
    ``denied``, ``not-required``→``not-required``, else ``unknown``) and stamped
    ``evidence=inferred``. Legacy values are **never written back silently**
    (M29 APV-1, F8 reject-never-coerce).
    """
    if record.authorization is not None:
        return record.authorization
    source = _LEGACY_APPROVAL_SOURCE[effective_approval(record)]
    return Authorization(
        source=source,
        deny=AuthorizationDeny.UNKNOWN if source is AuthorizationSource.DENIED else None,
        evidence=AuthorizationEvidence.INFERRED,
    )


def effective_permission_mode(record: AgentRecord) -> PermissionMode:
    """The permission mode recorded on a call, or ``unknown`` when not exposed.

    The mode is a time-varying fact; when a record does not carry it, the honest
    value is ``unknown`` — never inferred (M29 APV-2, F8). A caller with session
    context may reconstruct it from transition records
    (:func:`agentwatch.permission_mode.effective_modes`).
    """
    return record.permission_mode if record.permission_mode is not None else PermissionMode.UNKNOWN


def effective_record_phase(record: AgentRecord) -> RecordPhase:
    """The record's pre/post-execution phase, reading legacy records as ``unknown``.

    AAT requires pre-execution evidence for denials; when the phase was not
    proven at capture time the honest value is ``unknown`` — never inferred from
    ``outcome`` or the tool name (AAT-1, F8 reject-never-coerce). The value is
    never written back silently.
    """
    return record.record_phase if record.record_phase is not None else RecordPhase.UNKNOWN
