"""Injection-shaped-content heuristics (M28 DET-6, PRD 43 §DET-6).

Deterministic, offline signals over the content a harness exposes: a tool
result, tool arguments, an agent response, or a memory value. Two rules always
run — **instruction-override** phrasing and **hidden-instruction** markers
(invisible Unicode control/tag characters). A third, **imperative-density**, is
high-false-positive and therefore **off by default**, opted into per deployment.

These are signals, never verdicts: the anomaly links the source span and names
the rule; it does not encode content or block anything.
"""

from __future__ import annotations

import re

from analytics.config import settings
from analytics.detectors.base import BaseDetector
from analytics.models import Anomaly, RunSummary, SpanNode

# Content-bearing attributes that can smuggle an injection (metadata-only spans
# simply have none of these, so the detector is silent rather than guessing).
CONTENT_ATTRS: tuple[str, ...] = (
    "gen_ai.tool.result",
    "gen_ai.tool.arguments",
    "gen_ai.response.content",
    "gen_ai.memory.content",
)

_OVERRIDE_RE = re.compile(
    r"ignore (all )?(previous|prior|above) instructions?"
    r"|disregard (all )?(previous|prior|above)"
    r"|forget (all )?(previous|prior)"
    r"|you are now"
    r"|reveal your (system )?(prompt|instructions)"
    r"|new instructions?:",
    re.IGNORECASE,
)

# Invisible characters used to hide instructions from a human reader.
_HIDDEN_RANGES: tuple[tuple[int, int], ...] = (
    (0x200B, 0x200F),  # zero-width space/joiners + LRM
    (0x202A, 0x202E),  # bidi embedding/override
    (0x2066, 0x2069),  # bidi isolates
    (0xE0000, 0xE007F),  # Unicode tag characters
    (0xFEFF, 0xFEFF),  # zero-width no-break space / BOM
)

_IMPERATIVE_VERBS = frozenset(
    {
        "delete",
        "remove",
        "exfiltrate",
        "wipe",
        "drop",
        "overwrite",
        "disable",
        "reveal",
        "send",
        "upload",
        "curl",
        "download",
        "execute",
    }
)


def _override_rules(text: str) -> list[str]:
    return ["instruction-override"] if _OVERRIDE_RE.search(text) else []


def _hidden_rules(text: str) -> list[str]:
    for char in text:
        code = ord(char)
        if any(start <= code <= end for start, end in _HIDDEN_RANGES):
            return ["hidden-instruction"]
    return []


def _imperative_density_rules(text: str, threshold: float) -> list[str]:
    sentences = [part.strip() for part in re.split(r"[.!?\n]+", text) if part.strip()]
    if len(sentences) < 3:
        return []
    imperative = sum(
        1 for sentence in sentences if sentence.split()[0].lower() in _IMPERATIVE_VERBS
    )
    if imperative / len(sentences) >= threshold:
        return ["imperative-density"]
    return []


class InjectionShapeDetector(BaseDetector):
    """Flag injection-shaped content in a run's exposed content attributes."""

    anomaly_type = "injection-shape"

    def __init__(
        self,
        *,
        imperative_density_enabled: bool | None = None,
        imperative_threshold: float | None = None,
    ) -> None:
        self.imperative_density_enabled = (
            settings.detector_injection_imperative_enabled
            if imperative_density_enabled is None
            else imperative_density_enabled
        )
        self.imperative_threshold = (
            settings.detector_injection_imperative_threshold
            if imperative_threshold is None
            else imperative_threshold
        )

    def _rules_for(self, text: str) -> list[str]:
        rules = _override_rules(text) + _hidden_rules(text)
        if self.imperative_density_enabled:
            rules += _imperative_density_rules(text, self.imperative_threshold)
        return rules

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        sources: list[dict[str, object]] = []
        all_rules: set[str] = set()
        for span in self._walk_spans(spans):
            for attr in CONTENT_ATTRS:
                value = span.attributes.get(attr)
                if not isinstance(value, str) or not value:
                    continue
                rules = self._rules_for(value)
                if not rules:
                    continue
                all_rules.update(rules)
                sources.append(
                    {
                        "span_id": span.span_id,
                        "tool": str(span.attributes.get("gen_ai.tool.name", "")) or None,
                        "attribute": attr,
                        "rules": rules,
                    }
                )
        if not sources:
            return None
        severity = (
            "warning" if all_rules & {"instruction-override", "hidden-instruction"} else "info"
        )
        return self._build_anomaly(
            summary,
            severity,
            f"injection-shaped content in {len(sources)} span(s)",
            {
                "count": len(sources),
                "rules": sorted(all_rules),
                "sources": sources,
            },
        )
