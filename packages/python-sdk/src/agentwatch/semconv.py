"""Pinned OTel GenAI semantic-convention version (M22 W4, PRD 39).

GenAI semconv is Development-grade and moving; a moving target under a stability
claim is a support burden and a credibility risk. agentwatch **pins** the version
it emits, carries it in exported resource attributes and ``--version``, and ships
a drift check that flags upstream changes instead of breaking silently. The
security-event vocabulary is proposed upstream (DD-05) rather than improvised.

The pinned constant is the single source of truth; ``otel_component`` re-exports
it so there is one place to move it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from agentwatch.attrs import AGENT_SPAN_OPERATIONS

# The GenAI semantic-convention version agentwatch emits against. Re-pinned for
# v0.2.0 to the semantic-conventions-genai agent-span vocabulary (OTEL-1).
SEMCONV_VERSION = "1.37.0"

# The `gen_ai.*` attribute keys agentwatch emits today (see docs/design/otel-mapping.md).
PINNED_ATTRIBUTES: tuple[str, ...] = (
    "gen_ai.operation.name",
    "gen_ai.agent.name",
    "gen_ai.agent.version",
    "gen_ai.conversation.id",
    "gen_ai.request.model",
    "gen_ai.tool.name",
    "gen_ai.usage.total_tokens",
)


@dataclass(frozen=True)
class DriftReport:
    """The result of comparing emitted attributes against an upstream set."""

    version: str
    missing: tuple[str, ...] = ()
    extra: tuple[str, ...] = ()
    known: tuple[str, ...] = field(default_factory=tuple)

    @property
    def drifted(self) -> bool:
        return bool(self.missing)

    def to_dict(self) -> dict[str, object]:
        return {
            "pinned_version": self.version,
            "missing": list(self.missing),
            "extra": list(self.extra),
            "drifted": self.drifted,
        }


def version_line() -> str:
    """The pinned-version suffix shown by ``agentwatch --version``."""
    return f"OTel GenAI semconv {SEMCONV_VERSION}"


def check_drift(upstream_attributes: Iterable[str]) -> DriftReport:
    """Compare the pinned attribute set against an upstream set.

    An upstream attribute we emit that is *gone* is drift (``missing``); a new
    upstream attribute is informational (``extra``) and never fails the check.
    """
    return _drift(PINNED_ATTRIBUTES, upstream_attributes)


def check_operation_drift(upstream_operations: Iterable[str]) -> DriftReport:
    """Compare the canonical agent-span operations against an upstream set (OTEL-1).

    A canonical operation that upstream no longer defines is drift; a new upstream
    operation is informational. The drift check fails on a simulated upstream bump.
    """
    return _drift(AGENT_SPAN_OPERATIONS, upstream_operations)


def _drift(pinned: tuple[str, ...], upstream: Iterable[str]) -> DriftReport:
    known = set(upstream)
    missing = tuple(sorted(attr for attr in pinned if attr not in known))
    extra = tuple(sorted(attr for attr in known if attr not in pinned))
    return DriftReport(version=SEMCONV_VERSION, missing=missing, extra=extra, known=pinned)


__all__ = [
    "AGENT_SPAN_OPERATIONS",
    "PINNED_ATTRIBUTES",
    "SEMCONV_VERSION",
    "DriftReport",
    "check_drift",
    "check_operation_drift",
    "version_line",
]
