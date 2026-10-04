"""Soak-harness tests (M12 K4, NFR-7)."""

from __future__ import annotations

from pathlib import Path

from agentwatch.soak import run_soak


def test_small_soak_is_within_bounds(tmp_path: Path) -> None:
    report = run_soak(tmp_path / "records.jsonl", count=2000)

    assert report.within_bounds
    assert report.records == 2000
    assert report.size_mb > 0
    assert report.verify_seconds >= 0


def test_store_size_grows_roughly_linearly(tmp_path: Path) -> None:
    small = run_soak(tmp_path / "a.jsonl", count=1000)
    large = run_soak(tmp_path / "b.jsonl", count=2000)

    ratio = large.size_mb / small.size_mb
    assert 1.5 < ratio < 2.5, ratio


def test_soak_records_checkpointed_chain_stays_verifiable(tmp_path: Path) -> None:
    report = run_soak(tmp_path / "records.jsonl", count=2500)

    assert report.within_bounds
