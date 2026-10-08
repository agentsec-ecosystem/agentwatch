"""Incident-registry taxonomy mapping (M27 COR-2, #345).

Aligns agentwatch security events with the **Agent Incident Registry (AIR)**
schema fields (architecture / mechanism / control / agency / outcome) and the AI
Incident Database's **GMF** taxonomy. The mapping is a pure lookup: every event
type has a correspondent or an explicit ``None`` — an omission is a bug, not a
silent gap. Registry-shaped *reports* are emitted by COR-3/COR-4; only the
mapping and optional ``annotate`` incident tags live here (metadata-only).
"""

from __future__ import annotations

from agentwatch.records import SecurityEventType

# The AIR schema fields every finding must be expressible against.
AIR_FIELDS: tuple[str, ...] = ("architecture", "mechanism", "control", "agency", "outcome")

# agentwatch event type -> AIR field values. ``None`` means "no correspondent"
# (explicit, never silent). Values are our alignment against the published AIR
# schema (arXiv 2609.11030).
AIR_BY_EVENT: dict[str, dict[str, str] | None] = {
    SecurityEventType.DENIED.value: {
        "architecture": "agent-runtime",
        "mechanism": "permission-check",
        "control": "access-control",
        "agency": "human",
        "outcome": "blocked",
    },
    SecurityEventType.POLICY_FIRED.value: {
        "architecture": "agent-runtime",
        "mechanism": "policy-evaluation",
        "control": "policy",
        "agency": "system",
        "outcome": "flagged",
    },
    SecurityEventType.SECRET_DETECTED.value: {
        "architecture": "agent-runtime",
        "mechanism": "secret-scan",
        "control": "data-protection",
        "agency": "system",
        "outcome": "masked",
    },
    SecurityEventType.REVOKED.value: {
        "architecture": "credential",
        "mechanism": "credential-revocation",
        "control": "credential-lifecycle",
        "agency": "human",
        "outcome": "revoked",
    },
    SecurityEventType.HALTED.value: {
        "architecture": "agent-runtime",
        "mechanism": "kill-switch",
        "control": "availability",
        "agency": "human",
        "outcome": "halted",
    },
    SecurityEventType.DRIFT_DETECTED.value: {
        "architecture": "agent-runtime",
        "mechanism": "baseline-deviation",
        "control": "monitoring",
        "agency": "system",
        "outcome": "observed",
    },
    SecurityEventType.TOOL_SURFACE_CHANGED.value: {
        "architecture": "mcp-server",
        "mechanism": "tool-surface-drift",
        "control": "supply-chain",
        "agency": "external",
        "outcome": "observed",
    },
    SecurityEventType.AGENT_DELEGATION.value: {
        "architecture": "agent-runtime",
        "mechanism": "delegation",
        "control": "identity",
        "agency": "external",
        "outcome": "observed",
    },
    SecurityEventType.RECORDER_CONFIG_CHANGED.value: {
        "architecture": "agent-runtime",
        "mechanism": "recorder-config-change",
        "control": "recording-integrity",
        "agency": "system",
        "outcome": "observed",
    },
    SecurityEventType.MODE_TRANSITION.value: {
        "architecture": "agent-runtime",
        "mechanism": "permission-mode-transition",
        "control": "access-control",
        "agency": "human",
        "outcome": "observed",
    },
    SecurityEventType.CAPABILITY_CHANGED.value: {
        "architecture": "agent-runtime",
        "mechanism": "capability-inventory-change",
        "control": "supply-chain",
        "agency": "external",
        "outcome": "observed",
    },
    SecurityEventType.SANDBOX_BOUNDARY.value: {
        "architecture": "agent-runtime",
        "mechanism": "sandbox-boundary",
        "control": "sandbox",
        "agency": "system",
        "outcome": "observed",
    },
}

# GMF taxonomy category per event type. ``None`` is explicit: our alignment is
# not yet pinned for that event, so we never guess (pinning is tracked with the
# registry work, COR-3/COR-4).
GMF_BY_EVENT: dict[str, str | None] = {
    SecurityEventType.DENIED.value: "Misuse",
    SecurityEventType.POLICY_FIRED.value: "Misuse",
    SecurityEventType.SECRET_DETECTED.value: "Data leak",
    SecurityEventType.REVOKED.value: "Access control",
    SecurityEventType.HALTED.value: "Availability",
    SecurityEventType.DRIFT_DETECTED.value: None,
    SecurityEventType.TOOL_SURFACE_CHANGED.value: None,
    SecurityEventType.AGENT_DELEGATION.value: None,
    SecurityEventType.RECORDER_CONFIG_CHANGED.value: None,
    SecurityEventType.MODE_TRANSITION.value: "Access control",
    SecurityEventType.CAPABILITY_CHANGED.value: None,
    SecurityEventType.SANDBOX_BOUNDARY.value: "Access control",
}


def air_mapping(event_type: SecurityEventType) -> dict[str, str] | None:
    """The AIR field mapping for an event type (``None`` when no correspondent)."""
    return AIR_BY_EVENT[event_type.value]


def gmf_mapping(event_type: SecurityEventType) -> str | None:
    """The GMF taxonomy category for an event type (``None`` when unpinned)."""
    return GMF_BY_EVENT[event_type.value]


__all__ = ["AIR_BY_EVENT", "AIR_FIELDS", "GMF_BY_EVENT", "air_mapping", "gmf_mapping"]
