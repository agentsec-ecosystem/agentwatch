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

# The GenAI semantic-convention version agentwatch emits against.
SEMCONV_VERSION = "1.29.0"

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
    upstream = set(upstream_attributes)
    missing = tuple(sorted(attr for attr in PINNED_ATTRIBUTES if attr not in upstream))
    extra = tuple(sorted(attr for attr in upstream if attr not in PINNED_ATTRIBUTES))
    return DriftReport(
        version=SEMCONV_VERSION, missing=missing, extra=extra, known=PINNED_ATTRIBUTES
    )


__all__ = [
    "PINNED_ATTRIBUTES",
    "SEMCONV_VERSION",
    "DriftReport",
    "check_drift",
    "version_line",
]
