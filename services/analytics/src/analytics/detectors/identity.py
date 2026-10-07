"""Credential-hygiene detector (M28 IDN-4, PRD 44 §IDN-4).

A deterministic observation that a run acted under a **shared/ambient**
credential (``credential_class: ambient/shared``) — NIST's pre-Q4-2026 audit
ask for non-human identities. It is an observation, not a verdict: it names the
class the trace stated and never infers a credential the record did not carry.

The credential class arrives on spans via
``agentwatch.credential_class`` (``agentwatch.attrs`` in the SDK); absent stays
honestly unknown, so the detector is silent rather than guessing.
"""

from __future__ import annotations

from analytics.detectors.base import BaseDetector
from analytics.models import Anomaly, RunSummary, SpanNode

# The exported attribute that carries IDN-1's ``credential_class``.
CREDENTIAL_CLASS_ATTR = "agentwatch.credential_class"
AMBIENT_SHARED = "ambient/shared"


class CredentialHygieneDetector(BaseDetector):
    """Flag a run that acted under a shared/ambient credential."""

    anomaly_type = "credential-hygiene"

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        offenders = [
            span
            for span in self._walk_spans(spans)
            if str(span.attributes.get(CREDENTIAL_CLASS_ATTR, "")).strip().lower() == AMBIENT_SHARED
        ]
        if not offenders:
            return None
        tools = sorted(
            {
                str(span.attributes.get("gen_ai.tool.name", "")).strip()
                for span in offenders
                if str(span.attributes.get("gen_ai.tool.name", "")).strip()
            }
        )
        return self._build_anomaly(
            summary,
            "warning",
            f"shared/ambient credential used by {len(offenders)} span(s)",
            {
                "count": len(offenders),
                "credential_class": AMBIENT_SHARED,
                "tools": tools,
            },
        )
