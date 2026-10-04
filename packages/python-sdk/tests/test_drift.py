"""Trailing-baseline drift + deployment correlation tests (M11 R13, #89/#90)."""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

import agentwatch.hook as hook_module
from agentwatch.drift import (
    Deployment,
    DriftSignal,
    Sample,
    correlate_deployments,
    detect_drift,
    emit_signals,
    load_deployments,
    metric_series,
    signal_to_event,
    trailing_baseline,
)
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    SecurityEventType,
    StepType,
    ToolCall,
)
from agentwatch.store import RecordStore

BASE = datetime(2026, 1, 2, 3, 0, 0, tzinfo=timezone.utc)


def _sample(index: int, value: float) -> Sample:
    return Sample(at=BASE + timedelta(minutes=index), value=value)


def _record(
    session: str, outcome: Outcome = Outcome.OK, duration: float | None = None
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent-1"),
        tool=ToolCall(name="Bash"),
        outcome=outcome,
        started_at=BASE,
        step_type=StepType.ACT,
        duration_ms=duration,
    )


def test_trailing_baseline_stats() -> None:
    baseline = trailing_baseline([_sample(i, float(i)) for i in range(4)], window=4)
    assert baseline is not None
    assert baseline.count == 4
    assert baseline.mean == 1.5
    assert baseline.stdev == pytest.approx(1.118, abs=1e-3)
    assert trailing_baseline([], window=5) is None


def test_detect_drift_flags_a_shift_against_trailing_baseline() -> None:
    values = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 50.0]
    signals = detect_drift("errors", [_sample(i, v) for i, v in enumerate(values)], z_threshold=3.0)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.direction == "up"
    assert signal.value == 50.0
    assert signal.baseline_mean == pytest.approx(0.5)
    assert signal.z_score > 3.0


def test_a_spike_is_not_in_its_own_baseline() -> None:
    values = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 50.0, 0.0]
    signals = detect_drift("errors", [_sample(i, v) for i, v in enumerate(values)])
    # The spike at index 10 must not become the baseline for index 11.
    assert [signal.value for signal in signals] == [50.0]


def test_low_volume_series_stay_silent() -> None:
    assert detect_drift("errors", [_sample(i, 0.0) for i in range(3)], min_samples=5) == []


def test_zero_variance_baseline_does_not_divide_by_zero() -> None:
    assert detect_drift("errors", [_sample(i, 2.0) for i in range(12)]) == []


def test_signal_to_event_is_a_drift_detected_event() -> None:
    signal = detect_drift(
        "errors",
        [_sample(i, v) for i, v in enumerate([0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 50])],
    )[0]
    event = signal_to_event(signal)

    assert event.type is SecurityEventType.DRIFT_DETECTED
    assert event.tool == "errors"
    assert event.evidence is not None
    assert event.evidence["direction"] == "up"


def test_emit_signals_never_raises_and_counts_deliveries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []

    def fake_send(message: dict[str, Any], **_: object) -> bool:
        sent.append(message)
        return True

    monkeypatch.setattr(hook_module, "send", fake_send)
    signal = detect_drift(
        "errors", [_sample(i, v) for i, v in enumerate([0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 50])]
    )[0]

    assert emit_signals([signal]) == 1
    assert sent[0]["phase"] == "event"
    assert sent[0]["event"]["type"] == "drift-detected"


def test_correlate_deployments_matches_only_prior_window() -> None:
    signal = DriftSignal(
        metric="errors",
        at=BASE + timedelta(minutes=60),
        value=9.0,
        baseline_mean=0.5,
        baseline_stdev=0.5,
        z_score=17.0,
        direction="up",
        window=10,
    )
    deployments = [
        Deployment(at=BASE, label="in-window"),
        Deployment(at=BASE + timedelta(minutes=70), label="after"),
        Deployment(at=BASE - timedelta(hours=5), label="too-old"),
    ]

    correlated = correlate_deployments([signal], deployments, window_seconds=3600.0)

    assert [item.signal for item in correlated] == [signal]
    assert [deployment.label for deployment in correlated[0].deployments] == ["in-window"]


def test_load_deployments_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "deploys.jsonl"
    path.write_text(
        json.dumps({"at": "2026-01-02T03:00:00+00:00", "label": "v2", "version": "2.0"})
        + "\n"
        + json.dumps({"timestamp": "2026-01-02T04:00:00+00:00", "name": "v3"})
        + "\n",
        encoding="utf-8",
    )
    deployments = load_deployments(path)
    assert [deployment.label for deployment in deployments] == ["v2", "v3"]
    assert deployments[0].version == "2.0"


def test_metric_series_by_session_counts_errors() -> None:
    records = [
        _record("s1", Outcome.OK),
        _record("s1", Outcome.ERROR),
        _record("s2", Outcome.OK),
        _record("s3", Outcome.DENIED, duration=10.0),
    ]
    errors = metric_series(records, "errors", bucket="session")
    assert [sample.value for sample in errors] == [1.0, 0.0, 0.0]
    denied = metric_series(records, "denied", bucket="session")
    assert [sample.value for sample in denied] == [0.0, 0.0, 1.0]


def test_metric_series_rejects_unknown_metric() -> None:
    with pytest.raises(ValueError):
        metric_series([], "bogus")


def test_cli_drift_reports_a_signal_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main = importlib.import_module("agentwatch.cli.main")
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path))
    store = RecordStore(tmp_path / "records.jsonl")
    # Ten baseline sessions alternating 0/1 errors, then a spike of 8 errors.
    for index in range(10):
        store.append(_record(f"s{index}", Outcome.ERROR if index % 2 else Outcome.OK))
    for _ in range(8):
        store.append(_record("s10", Outcome.ERROR))

    assert main.main(["drift", "--metric", "errors", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["samples"] == 11
    assert payload["signals"][0]["direction"] == "up"
