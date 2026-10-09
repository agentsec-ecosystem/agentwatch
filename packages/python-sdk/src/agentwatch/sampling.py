"""Security-relevant-always-on sampler (M25 SDK-2, PRD 46).

Cost control that cannot discard evidence. Ordinary successful steps are
ratio-sampled **deterministically** (same decision across replays, like OTel
``TraceIdRatioBased``); security events, denials, errors, and approval decisions
are **never** sampled out. The decision is explicit so ``coverage`` (S2) can tell
"not recorded" apart from "recorded then dropped" — no silent gaps.
"""

from __future__ import annotations

import hashlib
from enum import Enum

from agentwatch.records import AgentRecord, Outcome


class SampleDecision(str, Enum):
    """The sampler's explicit verdict for one record."""

    ALWAYS = "always"  # security-relevant: kept regardless of ratio
    SAMPLED = "sampled"  # ordinary step, kept by the ratio
    SAMPLED_OUT = "sampled-out"  # ordinary step, dropped by the ratio


def is_security_relevant(record: AgentRecord) -> bool:
    """Whether a record carries evidence that must never be sampled away."""
    if record.security_event is not None:
        return True
    if record.outcome in (Outcome.DENIED, Outcome.ERROR):
        return True
    # Any recorded authorization decision is evidence (never inferred, never dropped).
    return record.approval is not None


class SecurityRelevantSampler:
    """A deterministic, evidence-preserving sampler."""

    def should_sample(self, record: AgentRecord, *, ratio: float) -> SampleDecision:
        """The sampling verdict for ``record`` at ``ratio`` (0.0–1.0)."""
        if is_security_relevant(record):
            return SampleDecision.ALWAYS
        kept = self._keep_by_ratio(record, ratio)
        return SampleDecision.SAMPLED if kept else SampleDecision.SAMPLED_OUT

    def _keep_by_ratio(self, record: AgentRecord, ratio: float) -> bool:
        if ratio >= 1.0:
            return True
        if ratio <= 0.0:
            return False
        step = record.span_id or record.tool.name
        key = f"{record.session_id}:{step}"
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        position = int.from_bytes(digest[:4], "big") / 2**32
        return position < ratio


__all__ = [
    "SampleDecision",
    "SecurityRelevantSampler",
    "is_security_relevant",
]