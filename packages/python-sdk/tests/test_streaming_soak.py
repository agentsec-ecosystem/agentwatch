"""Streaming soak tests (M26 STR-3, #320).

A bounded consumer that is starved, reconnects, and is backpressured must never
lose a stored record: every seq is eventually reconciled from the store, and the
queue stays bounded with ``degraded`` surfaced.
"""

from __future__ import annotations

from pathlib import Path

from agentwatch.streaming_soak import run_streaming_soak


def test_streaming_soak_no_store_loss_and_bounded(tmp_path: Path) -> None:
    report = run_streaming_soak(
        tmp_path / "records.jsonl", count=1000, hub_size=8, poll_every=50
    )

    assert report.records == 1000
    assert report.delivered == 1000  # every record reconciled; none lost
    assert report.degraded_polls >= 1  # backpressure surfaced, never silent
    assert report.within_bounds is True


def test_streaming_soak_reconnect_does_not_lose_records(tmp_path: Path) -> None:
    report = run_streaming_soak(
        tmp_path / "records.jsonl",
        count=500,
        hub_size=4,
        poll_every=25,
        reconnect_every=100,
    )

    assert report.delivered == report.records
    assert report.within_bounds is True


def test_streaming_soak_pacing_uses_injected_sleep(tmp_path: Path) -> None:
    slept: list[float] = []

    report = run_streaming_soak(
        tmp_path / "records.jsonl",
        count=10,
        poll_every=0,
        pace_seconds=0.5,
        sleep=slept.append,
    )

    assert slept == [0.5] * 10
    assert report.delivered == 10


def test_streaming_soak_script_runs() -> None:
    import importlib.util
    import sys

    path = Path(__file__).resolve().parents[3] / "scripts" / "streaming_soak.py"
    spec = importlib.util.spec_from_file_location("streaming_soak_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    assert module.main(["--count", "200", "--poll-every", "50"]) == 0
