"""ACS Guardian audit-trail ingest (M29 ACS-1, #367).

The **Agent Control Standard** (ACS, `GenAI-Security-Project/agent-control-standard`)
is a JSON-RPC 2.0 wire spec: an Observed Agent sends every step to a Guardian over
``steps/*`` (e.g. ``steps/toolCallRequest``) and the Guardian returns a decision —
``allow`` / ``deny`` / ``modify`` / ``ask`` / ``defer``. Those decisions are the
security events agentwatch already models, with AAT ``record_phase:
pre_execution``: the Guardian decides *before* the action it gates.

This is an **ingest reader** for a Guardian's audit trail. It is monitor-only:
we record a decision, we never execute it (enforcement stays in the Guardian).
The spec is young, so the revision is **pinned** (``ACS_VERSION``) and a moved or
narrowed spec fails :func:`check_acs_drift` (the AAT-5 pattern); an unknown frame,
method, revision, or decision is quarantined with a reason (never invented). The
trail is untrusted foreign input: content is masked through the secrets pipeline
before storage (DD-06).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from agentwatch.ingest import IngestProblem
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    Producer,
    ProducerKind,
    RecordPhase,
    RecordPrivacyMode,
    SecurityEvent,
    SecurityEventType,
    StepType,
    ToolCall,
    _parse_iso,
    validate_record,
)
from agentwatch.redact import PrivacyMode, RedactionConfig
from agentwatch.secrets import redact_mapping

HARNESS_ID = "acs"
ACS_PRODUCER = Producer(kind=ProducerKind.INGEST, name=HARNESS_ID)

# The pinned ACS revision (PRD 45 §ACS-1: "spec is young → version-pin + drift").
ACS_VERSION = "0.1.0"

# Monitor-only is a guarantee, not a default: agentwatch never executes a decision,
# and the emit-side spike (PRD 45 §ACS-1b) is not built.
MONITOR_ONLY = True
EMIT_SIDE_BUILT = False

# The ACS fields our mapping targets (published). A revision that drops one is
# drift and fails the pin check (AAT-5 pattern).
ACS_SPEC_FIELDS: tuple[str, ...] = (
    "acs_version",
    "request_id",
    "timestamp",
    "metadata",
    "payload",
    "decision",
)

# ACS concept -> agentwatch source. Published in docs/design/acs-interop.md.
ACS_MAPPING: dict[str, str] = {
    "decision=deny": "SecurityEventType.denied (outcome=denied)",
    "decision=modify/ask/defer": "SecurityEventType.policy-fired",
    "decision=allow": "record only, no security event",
    "record_phase": "pre_execution (the Guardian decides before the gated action)",
    "metadata.session_id": "record session_id",
    "metadata.agent_id": "agent_identity.identity",
    "payload.tool.name": "tool name",
    "policy_references": "security_event.policy_id + evidence",
    "reasoning / reason_codes": "security_event.reason + evidence",
}

# The 19 ACS v0.1.0 ``steps/*`` hooks (Specification §5). An unknown hook is a
# foreign frame we do not map; ``protocols/MCP/*`` wrapping is open-ended.
ACS_STEP_HOOKS: frozenset[str] = frozenset(
    {
        "sessionStart",
        "agentTrigger",
        "turnStart",
        "userMessage",
        "agentResponse",
        "knowledgeRetrieval",
        "memoryContextRetrieval",
        "memoryStore",
        "toolCallRequest",
        "toolCallResult",
        "preCompact",
        "postCompact",
        "subagentStart",
        "subagentStop",
        "skillRegister",
        "skillLoad",
        "skillUnload",
        "turnEnd",
        "sessionEnd",
    }
)
_DECISIONS = frozenset({"allow", "deny", "modify", "ask", "defer"})
_DENY_DECISIONS = frozenset({"deny"})
_NON_ALLOW_DECISIONS = frozenset({"deny", "modify", "ask", "defer"})

_PRIVACY_MAP = {
    PrivacyMode.METADATA_ONLY: RecordPrivacyMode.METADATA_ONLY,
    PrivacyMode.TRUNCATED: RecordPrivacyMode.TRUNCATED,
    PrivacyMode.HASHED: RecordPrivacyMode.HASHED,
    PrivacyMode.FULL: RecordPrivacyMode.FULL,
}


class AcsError(ValueError):
    """Raised when an ACS frame cannot be mapped."""


# ---------------------------------------------------------------------------
# Version pin + drift
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ACSDriftReport:
    """The result of comparing our pinned revision against an upstream descriptor."""

    pinned: str
    upstream: str
    missing: tuple[str, ...] = ()
    extra: tuple[str, ...] = ()

    @property
    def drifted(self) -> bool:
        """Drift when the revision moved or an upstream field we map has gone."""
        return self.pinned != self.upstream or bool(self.missing)

    def to_dict(self) -> dict[str, object]:
        return {
            "pinned_revision": self.pinned,
            "upstream_revision": self.upstream,
            "missing": list(self.missing),
            "extra": list(self.extra),
            "drifted": self.drifted,
        }


def acs_version_line() -> str:
    """The pinned-revision suffix shown in ``agentwatch --version``."""
    return f"ACS {ACS_VERSION}"


def check_acs_drift(upstream: Any) -> ACSDriftReport:
    """Compare the pinned ACS revision against an upstream descriptor.

    The upstream descriptor is ``{"revision": "...", "fields": [...]}`` (the
    same shape AAT-5 uses). A revision bump, or a mapped field upstream dropped,
    is drift; a new upstream field is informational and never fails the check.
    """
    revision = "<unknown>"
    known: set[str] = set()
    has_fields = False
    if isinstance(upstream, Mapping):
        raw_revision = upstream.get("revision")
        if isinstance(raw_revision, str):
            revision = raw_revision
        fields = upstream.get("fields")
        if isinstance(fields, (list, tuple)):
            has_fields = True
            known = {str(field) for field in fields}
    missing = (
        tuple(sorted(field for field in ACS_SPEC_FIELDS if field not in known))
        if has_fields
        else ()
    )
    extra = tuple(sorted(field for field in known if field not in ACS_SPEC_FIELDS))
    return ACSDriftReport(pinned=ACS_VERSION, upstream=revision, missing=missing, extra=extra)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def is_acs_record(record: AgentRecord) -> bool:
    """Whether a record came from a foreign ACS Guardian audit trail."""
    environment = record.environment or {}
    return environment.get("source") == HARNESS_ID or (
        record.producer is not None and record.producer.name == HARNESS_ID
    )


def _messages(payload: Any, source: str) -> tuple[list[Mapping[str, Any]], list[IngestProblem]]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            return [], [IngestProblem(source, f"invalid JSON: {exc}")]
    if isinstance(payload, Mapping):
        messages = payload.get("messages")
        if isinstance(messages, list):
            return [m for m in messages if isinstance(m, Mapping)], []
        return [payload], []
    if isinstance(payload, list):
        return [m for m in payload if isinstance(m, Mapping)], []
    return [], [IngestProblem(source, "ACS payload is not a message or a message list")]


def _known_method(method: str) -> bool:
    """Whether an ACS method is one we map (a step hook or a wrapped protocol)."""
    if method.startswith("protocols/"):
        return True
    if method.startswith("steps/"):
        return method.split("/", 1)[1] in ACS_STEP_HOOKS
    return False


def _frame_id(message: Mapping[str, Any]) -> str | None:
    raw = message.get("id")
    if isinstance(raw, str) and raw:
        return raw
    for key in ("params", "result"):
        inner = message.get(key)
        if isinstance(inner, Mapping):
            request_id = inner.get("request_id")
            if isinstance(request_id, str) and request_id:
                return request_id
    return None


def _timestamp(value: Any) -> datetime:
    if isinstance(value, str) and value:
        try:
            return _parse_iso(value)
        except ValueError:
            pass
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = value / 1e9 if value > 1e12 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    return datetime.now(timezone.utc)


def _revision(value: Any) -> str:
    return value if isinstance(value, str) and value else "<missing>"


def _redact(value: Any, cfg: RedactionConfig) -> Any:
    if isinstance(value, str):
        return cfg.apply(value, allowed=True)
    if isinstance(value, Mapping):
        return {key: _redact(item, cfg) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, cfg) for item in value]
    return value


def _captured(
    arguments: Mapping[str, Any], cfg: RedactionConfig | None
) -> tuple[dict[str, Any] | None, RecordPrivacyMode]:
    if cfg is None or cfg.mode is PrivacyMode.METADATA_ONLY or not cfg.capture_tool_args:
        return None, RecordPrivacyMode.METADATA_ONLY
    masked, _ = redact_mapping(dict(arguments))
    return _redact(masked, cfg), _PRIVACY_MAP[cfg.mode]


def _security_event(
    decision: str,
    *,
    tool: str,
    at: datetime,
    result: Mapping[str, Any],
    kinds: list[str],
) -> SecurityEvent | None:
    evidence: dict[str, Any] = {"acs_version": ACS_VERSION}
    if kinds:
        evidence["secret_kinds"] = kinds
    reason_codes = result.get("reason_codes")
    if isinstance(reason_codes, list):
        evidence["reason_codes"] = [str(code) for code in reason_codes]
    policies = result.get("policy_references")
    policy_id: str | None = None
    if isinstance(policies, list) and policies:
        evidence["policy_references"] = policies
        first = policies[0]
        if isinstance(first, Mapping) and isinstance(first.get("policy_id"), str):
            policy_id = first["policy_id"]
    raw_reasoning = result.get("reasoning")
    reason = raw_reasoning if isinstance(raw_reasoning, str) and raw_reasoning else None

    if decision in _NON_ALLOW_DECISIONS:
        event_type = (
            SecurityEventType.DENIED
            if decision in _DENY_DECISIONS
            else SecurityEventType.POLICY_FIRED
        )
        return SecurityEvent(
            type=event_type,
            emitted_at=at,
            emitter=HARNESS_ID,
            reason=reason,
            policy_id=policy_id,
            tool=tool,
            evidence=evidence,
        )
    if kinds:
        return SecurityEvent(
            type=SecurityEventType.SECRET_DETECTED,
            emitted_at=at,
            emitter="agentwatch",
            tool=tool,
            evidence={"kinds": kinds},
        )
    return None


def _decision_record(
    request: Mapping[str, Any],
    response: Mapping[str, Any],
    *,
    redaction: RedactionConfig | None,
) -> AgentRecord:
    method = request.get("method")
    if not isinstance(method, str) or not _known_method(method):
        raise AcsError(f"unmappable ACS method {method!r}")
    params = request.get("params")
    if not isinstance(params, Mapping):
        raise AcsError("ACS request has no params")
    revision = _revision(params.get("acs_version"))
    if revision != ACS_VERSION:
        raise AcsError(f"unsupported ACS revision: {revision!r}")

    result = response.get("result")
    result_revision = _revision(result.get("acs_version") if isinstance(result, Mapping) else None)
    if result_revision != ACS_VERSION:
        raise AcsError(f"unsupported ACS revision: {result_revision!r}")

    decision = result.get("decision")
    if not isinstance(decision, str) or decision not in _DECISIONS:
        raise AcsError(f"unmappable ACS decision {decision!r}")

    payload = params.get("payload")
    payload = payload if isinstance(payload, Mapping) else {}
    tool_block = payload.get("tool")
    tool = (
        tool_block.get("name")
        if isinstance(tool_block, Mapping) and isinstance(tool_block.get("name"), str)
        else method.split("/", 1)[1]
    )
    metadata = params.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    session = metadata.get("session_id")
    session_id = str(session) if isinstance(session, str) and session else HARNESS_ID
    agent_id = metadata.get("agent_id")
    identity = str(agent_id) if isinstance(agent_id, str) and agent_id else HARNESS_ID

    request_id = params.get("request_id") or result.get("request_id") or _frame_id(request)
    span_id = f"acs:{request_id}" if isinstance(request_id, str) and request_id else None

    at = _timestamp(params.get("timestamp"))
    masked, kinds = redact_mapping({"params": params, "result": result})
    masked_result = masked.get("result") if isinstance(masked, Mapping) else {}
    security_event = _security_event(
        decision,
        tool=str(tool),
        at=at,
        result=masked_result if isinstance(masked_result, Mapping) else result,
        kinds=list(kinds),
    )

    tool_kwargs: dict[str, Any] = {"name": str(tool)}
    arguments = payload.get("arguments")
    if isinstance(arguments, Mapping):
        captured, privacy_mode = _captured(arguments, redaction)
        if captured is not None:
            tool_kwargs["arguments"] = captured
            tool_kwargs["privacy_mode"] = privacy_mode

    capability = payload.get("capability")
    environment: dict[str, Any] = {
        "source": HARNESS_ID,
        "acs_version": ACS_VERSION,
        "method": method,
        "decision": decision,
        "monitor_only": MONITOR_ONLY,
    }
    if isinstance(capability, str) and capability:
        environment["capability"] = capability
    tenant = params.get("tenant_id")
    if isinstance(tenant, str) and tenant:
        environment["tenant_id"] = tenant

    outcome = Outcome.DENIED if decision in _DENY_DECISIONS else Outcome.OK
    record = AgentRecord(
        session_id=session_id,
        agent=AgentIdentity(identity=identity, name=identity if identity != HARNESS_ID else None),
        tool=ToolCall(**tool_kwargs),
        outcome=outcome,
        started_at=at,
        harness=HARNESS_ID,
        producer=ACS_PRODUCER,
        trace_id=session_id,
        span_id=span_id,
        step_type=StepType.OBSERVE,
        record_phase=RecordPhase.PRE_EXECUTION,
        environment=environment,
        security_event=security_event,
    )
    validate_record(record.to_dict())
    return record


def transcode_acs(
    payload: Any,
    *,
    source: str = HARNESS_ID,
    redaction: RedactionConfig | None = None,
) -> tuple[list[AgentRecord], list[IngestProblem]]:
    """Transcode an ACS Guardian audit trail into records + problems.

    Accepts ``{"messages": [...]}``, a list of JSON-RPC frames, a single frame, or
    a JSON string. Each Guardian decision response is paired to its request by
    ``id``/``request_id``; an unrecognized revision/method/decision, or a decision
    without its request, is a problem the caller quarantines (B4), never invented.
    """
    messages, problems = _messages(payload, source)
    requests: dict[str, Mapping[str, Any]] = {}
    for message in messages:
        if isinstance(message.get("method"), str):
            frame = _frame_id(message)
            if frame is not None:
                requests.setdefault(frame, message)

    records: list[AgentRecord] = []
    for index, message in enumerate(messages):
        result = message.get("result")
        if not isinstance(result, Mapping):
            continue  # a request/notification, not a decision
        frame = _frame_id(message)
        request = requests.get(frame) if frame is not None else None
        here = f"{source}#{index}"
        if request is None:
            problems.append(
                IngestProblem(here, "ACS decision frame without a matching request")
            )
            continue
        try:
            records.append(_decision_record(request, message, redaction=redaction))
        except (AcsError, KeyError, TypeError, ValueError) as exc:
            problems.append(IngestProblem(here, f"unmappable ACS frame: {exc}"))
    return records, problems


__all__ = [
    "ACS_MAPPING",
    "ACS_PRODUCER",
    "ACS_SPEC_FIELDS",
    "ACS_VERSION",
    "EMIT_SIDE_BUILT",
    "HARNESS_ID",
    "MONITOR_ONLY",
    "ACSDriftReport",
    "AcsError",
    "acs_version_line",
    "check_acs_drift",
    "is_acs_record",
    "transcode_acs",
]
