"""Fake-harness emitter tests (M10 N3 #214)."""

from __future__ import annotations

from pathlib import Path

import fake_harness
import pytest

from agentwatch.adapters import claude_code, codex_cli, cursor, gemini_cli, mcp_proxy
from agentwatch.daemon import Daemon
from agentwatch.records import validate_record
from agentwatch.store import RecordStore

_ADAPTERS = {
    "claude-code": claude_code,
    "cursor": cursor,
    "codex-cli": codex_cli,
    "gemini-cli": gemini_cli,
    "mcp-proxy": mcp_proxy,
}


def test_every_supported_platform_has_an_emitter() -> None:
    assert set(fake_harness.PLATFORMS) == set(_ADAPTERS)


@pytest.mark.parametrize("platform", fake_harness.PLATFORMS)
def test_platform_stream_normalizes_through_its_adapter(platform: str) -> None:
    adapter = _ADAPTERS[platform]
    events = list(fake_harness.realistic_stream(platform))

    assert events
    for event in events:
        for record in adapter.normalize(event):
            validate_record(record.to_dict())


def test_emitters_are_deterministic() -> None:
    first = list(fake_harness.realistic_stream("cursor", count=5, seed=7))
    second = list(fake_harness.realistic_stream("cursor", count=5, seed=7))

    assert first == second


def test_out_of_order_and_duplicates_do_not_crash_the_daemon(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    daemon = Daemon(
        socket_path=tmp_path / "d.sock",
        store=store,
        records_path=tmp_path / "records.jsonl",
    )

    for frame in fake_harness.out_of_order_stream("claude-code"):
        daemon.handle_message(frame)
    for frame in fake_harness.duplicate_stream("mcp-proxy"):
        daemon.handle_message(frame)

    assert store.verify().ok


def test_malformed_frames_are_quarantined(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    daemon = Daemon(
        socket_path=tmp_path / "d.sock",
        store=store,
        records_path=tmp_path / "records.jsonl",
    )

    for frame in fake_harness.malformed_stream():
        daemon.handle_message(frame)

    assert (tmp_path / "quarantine.jsonl").exists()
    assert store.verify().ok


def test_clock_skew_stream_records_without_crashing(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    daemon = Daemon(
        socket_path=tmp_path / "d.sock",
        store=store,
        records_path=tmp_path / "records.jsonl",
    )

    written = [daemon.handle_message(frame) for frame in fake_harness.clock_skew_stream()]

    assert any(records for records in written)
    assert store.verify().ok


def test_unknown_platform_is_rejected() -> None:
    with pytest.raises(KeyError):
        list(fake_harness.realistic_stream("nonexistent"))
