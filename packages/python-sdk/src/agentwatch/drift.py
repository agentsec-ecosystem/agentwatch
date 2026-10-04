"""Trailing-baseline drift signals + deployment correlation (M11 R13, #89/#90).

Drift is detected against a **trailing baseline** — the rolling mean/stdev of the
immediately preceding samples — never a fixed threshold (the AgentWatch #66
principle). A deviation beyond ``z_threshold`` becomes a :class:`DriftSignal`,
which is emitted as a ``drift-detected`` security event. Signals are
observations only: they never enforce, and the CLI exits ``0`` (PRD 14/30).

Deployment correlation overlays deploy markers: a shift is *correlated* with any
deploy that happened shortly before it, for a human to judge causation.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentwatch import hook
from agentwatch.records import (
    AgentRecord,
    Outcome,
    SecurityEvent,
    SecurityEventType,
    _parse_iso,
)

_METRICS = ("records", "errors", "denied", "duration")
_BUCKETS = ("session", "hour")


@dataclass(frozen=True)
class Sample:
    """One point in a metric time series."""

    at: datetime
    value: float


@dataclass(frozen=True)
class Baseline:
    """Trailing-baseline statistics."""

    mean: float
    stdev: float
    count: int


@dataclass(frozen=True)
class DriftSignal:
    """A metric value that deviated from its trailing baseline."""

    metric: str
    at: datetime
    value: float
    baseline_mean: float
    baseline_stdev: float
    z_score: float
    direction: str
    window: int


@dataclass(frozen=True)
class Deployment:
    """A deployment marker used to explain a nearby shift."""

    at: datetime
    label: str
    version: str | None = None


@dataclass(frozen=True)
class CorrelatedSignal:
    """A drift signal with the deployments that precede it within a window."""

    signal: DriftSignal
    deployments: tuple[Deployment, ...]


# ---------------------------------------------------------------------------
# Trailing-baseline detection
# ---------------------------------------------------------------------------


def trailing_baseline(samples: Sequence[Sample], *, window: int) -> Baseline | None:
    """Mean/stdev over the last ``window`` samples (population stdev)."""
    recent = list(samples[-window:]) if window > 0 else []
    if not recent:
        return None
    values = [sample.value for sample in recent]
    mean = statistics.fmean(values)
    stdev = statistics.pstdev(values) if len(values) > 1 else 0.0
    return Baseline(mean=mean, stdev=stdev, count=len(values))


def detect_drift(
    metric: str,
    samples: Sequence[Sample],
    *,
    window: int = 10,
    z_threshold: float = 3.0,
    min_samples: int = 5,
) -> list[DriftSignal]:
    """Flag samples deviating from their strictly-trailing baseline.

    A sample is never part of its own baseline, so a single spike cannot inflate
    the threshold that judges it. Low-volume series and zero-variance baselines
    stay silent (no divide-by-zero, no vacuous signal).
    """
    signals: list[DriftSignal] = []
    for index, current in enumerate(samples):
        if index < min_samples:
            continue
        prior = list(samples[max(0, index - window) : index])
        baseline = trailing_baseline(prior, window=window)
        if baseline is None or baseline.count < min_samples or baseline.stdev <= 0:
            continue
        z = (current.value - baseline.mean) / baseline.stdev
        if abs(z) >= z_threshold:
            signals.append(
                DriftSignal(
                    metric=metric,
                    at=current.at,
                    value=current.value,
                    baseline_mean=baseline.mean,
                    baseline_stdev=baseline.stdev,
                    z_score=z,
                    direction="up" if z > 0 else "down",
                    window=baseline.count,
                )
            )
    return signals


def signal_to_event(signal: DriftSignal) -> SecurityEvent:
    """Convert a drift signal into a ``drift-detected`` security event."""
    return SecurityEvent(
        type=SecurityEventType.DRIFT_DETECTED,
        emitted_at=signal.at,
        emitter="agentwatch",
        tool=signal.metric,
        reason=f"z={signal.z_score:.2f} over trailing {signal.window}",
        evidence={
            "metric": signal.metric,
            "value": signal.value,
            "baseline_mean": signal.baseline_mean,
            "baseline_stdev": signal.baseline_stdev,
            "z_score": signal.z_score,
            "direction": signal.direction,
            "window": signal.window,
        },
    )


def emit_signals(signals: Iterable[DriftSignal], *, socket_path: str | None = None) -> int:
    """Emit each signal's event to the daemon; return how many were delivered."""
    sent = 0
    for signal in signals:
        frame = {
            "phase": "event",
            "harness": "agentwatch",
            "event": signal_to_event(signal).to_dict(),
        }
        if hook.send(frame, socket_path=socket_path):
            sent += 1
    return sent


# ---------------------------------------------------------------------------
# Deployment correlation
# ---------------------------------------------------------------------------


def load_deployments(path: Path) -> list[Deployment]:
    """Load deployment markers from JSON (array) or JSONL."""
    text = path.read_text(encoding="utf-8")
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError:
        payload = [json.loads(line) for line in text.splitlines() if line.strip()]
    items = payload if isinstance(payload, list) else [payload]
    deployments: list[Deployment] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        at = item.get("at") or item.get("timestamp")
        if not isinstance(at, str):
            continue
        label = item.get("label") or item.get("name") or "deploy"
        version = item.get("version")
        deployments.append(
            Deployment(
                at=_parse_iso(at),
                label=str(label),
                version=str(version) if isinstance(version, str) else None,
            )
        )
    return sorted(deployments, key=lambda deployment: deployment.at)


def correlate_deployments(
    signals: Iterable[DriftSignal],
    deployments: Sequence[Deployment],
    *,
    window_seconds: float = 3600.0,
) -> list[CorrelatedSignal]:
    """Attach deployments that occurred within ``window_seconds`` before a shift."""
    correlated: list[CorrelatedSignal] = []
    for signal in signals:
        matched = tuple(
            deployment
            for deployment in deployments
            if 0.0 <= (signal.at - deployment.at).total_seconds() <= window_seconds
        )
        correlated.append(CorrelatedSignal(signal=signal, deployments=matched))
    return correlated


# ---------------------------------------------------------------------------
# Metric series from stored records
# ---------------------------------------------------------------------------


def metric_series(
    records: Iterable[AgentRecord], metric: str, *, bucket: str = "session"
) -> list[Sample]:
    """Build a metric time series from records, bucketed by session or hour."""
    if metric not in _METRICS:
        raise ValueError(f"unknown metric {metric!r}; expected one of {', '.join(_METRICS)}")
    if bucket not in _BUCKETS:
        raise ValueError(f"unknown bucket {bucket!r}; expected one of {', '.join(_BUCKETS)}")

    groups: dict[Any, dict[str, Any]] = {}
    for record in records:
        if bucket == "hour":
            key: Any = record.started_at.replace(minute=0, second=0, microsecond=0)
            at = key
        else:
            key = record.session_id
            at = record.started_at
        group = groups.setdefault(
            key, {"at": at, "count": 0, "errors": 0, "denied": 0, "durations": []}
        )
        if at < group["at"]:
            group["at"] = at
        group["count"] += 1
        if record.outcome is Outcome.ERROR:
            group["errors"] += 1
        elif record.outcome is Outcome.DENIED:
            group["denied"] += 1
        if record.duration_ms is not None:
            group["durations"].append(record.duration_ms)

    samples: list[Sample] = []
    for group in groups.values():
        if metric == "records":
            value = float(group["count"])
        elif metric == "errors":
            value = float(group["errors"])
        elif metric == "denied":
            value = float(group["denied"])
        else:  # duration
            durations = group["durations"]
            value = float(sum(durations) / len(durations)) if durations else 0.0
        samples.append(Sample(at=group["at"], value=value))
    return sorted(samples, key=lambda sample: sample.at)


def signal_to_json(signal: DriftSignal) -> dict[str, Any]:
    """Serialize a drift signal (with an ISO timestamp) for output."""
    return {
        "metric": signal.metric,
        "at": signal.at.astimezone(timezone.utc).isoformat(),
        "value": signal.value,
        "baseline_mean": signal.baseline_mean,
        "baseline_stdev": signal.baseline_stdev,
        "z_score": signal.z_score,
        "direction": signal.direction,
        "window": signal.window,
    }
