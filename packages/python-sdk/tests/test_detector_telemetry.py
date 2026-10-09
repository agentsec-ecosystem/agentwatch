"""Opt-in local detector telemetry tests (M27 DET-5 #344).

Detector telemetry is **opt-in**, **local-only**, and **content-free**: a marker
carries only the detector name, its verdict (fired/suppressed/false-positive),
and a timestamp — never any trace/prompt/argument content — so an operator can
measure detectors on their own corpus and feed the markers to a SIEM sink.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.detector_telemetry import (
    OUTCOME_FALSE_POSITIVE,
    OUTCOME_FIRED,
    OUTCOME_SUPPRESSED,
    DetectorTelemetry,
)

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def test_disabled_telemetry_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "telemetry.ndjson"
    telemetry = DetectorTelemetry(enabled=False, path=path)

    assert telemetry.record("loop", OUTCOME_FIRED, at=AT) is None
    assert not path.exists()


def test_enabled_marker_is_content_free(tmp_path: Path) -> None:
    path = tmp_path / "telemetry.ndjson"
    telemetry = DetectorTelemetry(enabled=True, path=path)

    marker = telemetry.record("loop", OUTCOME_FIRED, severity="warning", at=AT)

    assert marker is not None
    assert marker.to_dict() == {
        "kind": "detector-telemetry",
        "detector": "loop",
        "outcome": "fired",
        "severity": "warning",
        "at": "2026-01-02T03:04:05+00:00",
    }
    written = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert set(written) == {"kind", "detector", "outcome", "severity", "at"}


def test_all_three_outcomes_are_accepted(tmp_path: Path) -> None:
    telemetry = DetectorTelemetry(enabled=True, path=tmp_path / "t.ndjson")
    for outcome in (OUTCOME_FIRED, OUTCOME_SUPPRESSED, OUTCOME_FALSE_POSITIVE):
        marker = telemetry.record("retry", outcome, at=AT)
        assert marker is not None and marker.outcome == outcome


def test_invalid_outcome_and_empty_detector_are_rejected() -> None:
    telemetry = DetectorTelemetry(enabled=True)
    with pytest.raises(ValueError):
        telemetry.record("loop", "guessed")
    with pytest.raises(ValueError):
        telemetry.record("", OUTCOME_FIRED)


def test_telemetry_is_bounded(tmp_path: Path) -> None:
    path = tmp_path / "t.ndjson"
    telemetry = DetectorTelemetry(enabled=True, path=path, max_markers=2)

    assert telemetry.record("loop", OUTCOME_FIRED, at=AT) is not None
    assert telemetry.record("loop", OUTCOME_FIRED, at=AT) is not None
    assert telemetry.record("loop", OUTCOME_FIRED, at=AT) is None
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
