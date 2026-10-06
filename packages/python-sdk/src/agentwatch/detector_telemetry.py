"""Opt-in, content-free detector telemetry (M27 DET-5, PRD 43).

Operators must be able to measure our detectors on their **own** corpus without
shipping trace content anywhere: a marker records only the detector name, its
verdict (``fired`` / ``suppressed`` / ``false-positive``), an optional severity,
and a timestamp. It is **off by default**, **local-only** (an NDJSON file), and
**bounded** — a marker never carries arguments, prompts, or span content, so it
is safe to feed to a SIEM sink (:mod:`agentwatch.sinks`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OUTCOME_FIRED = "fired"
OUTCOME_SUPPRESSED = "suppressed"
OUTCOME_FALSE_POSITIVE = "false-positive"
OUTCOMES: frozenset[str] = frozenset({OUTCOME_FIRED, OUTCOME_SUPPRESSED, OUTCOME_FALSE_POSITIVE})

DEFAULT_MAX_MARKERS = 10_000


@dataclass(frozen=True)
class DetectorMarker:
    """One content-free detector observation."""

    detector: str
    outcome: str
    at: datetime
    severity: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "kind": "detector-telemetry",
            "detector": self.detector,
            "outcome": self.outcome,
            "at": self.at.isoformat(),
        }
        if self.severity is not None:
            data["severity"] = self.severity
        return data


@dataclass
class DetectorTelemetry:
    """An opt-in, bounded, local-only detector-marker sink.

    When ``enabled`` is false (the default) :meth:`record` is a no-op and writes
    nothing. When enabled it appends one content-free NDJSON line per marker to
    ``path`` (if set) and stops after ``max_markers`` to stay bounded.
    """

    enabled: bool = False
    path: Path | None = None
    max_markers: int = DEFAULT_MAX_MARKERS
    written: int = field(default=0, init=False)

    def record(
        self,
        detector: str,
        outcome: str,
        *,
        severity: str | None = None,
        at: datetime | None = None,
    ) -> DetectorMarker | None:
        """Record one marker, or return ``None`` when disabled/bounded.

        Raises:
            ValueError: an empty detector name or an unknown outcome — telemetry
                never guesses a verdict.
        """
        if not self.enabled or self.written >= self.max_markers:
            return None
        if not isinstance(detector, str) or not detector.strip():
            raise ValueError("detector must not be empty")
        if outcome not in OUTCOMES:
            raise ValueError(f"unknown outcome {outcome!r}; expected one of {sorted(OUTCOMES)}")
        marker = DetectorMarker(
            detector=detector.strip(),
            outcome=outcome,
            at=at or datetime.now(timezone.utc),
            severity=severity,
        )
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(marker.to_dict(), sort_keys=True) + "\n")
        self.written += 1
        return marker


__all__ = [
    "DEFAULT_MAX_MARKERS",
    "OUTCOME_FALSE_POSITIVE",
    "OUTCOME_FIRED",
    "OUTCOME_SUPPRESSED",
    "OUTCOMES",
    "DetectorMarker",
    "DetectorTelemetry",
]
