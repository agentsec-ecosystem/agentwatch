"""Recorder-state audit tests (M16 S5, #239).

Every recorder-state transition is a metadata-only marker in the chain, so a
deliberate uninstall or privacy downgrade is never indistinguishable from an idle
laptop. Markers coalesce, carry no secret value, and the coverage window pairs
open/close (an unclosed window stays open, never silently complete).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.configuration import load_config
from agentwatch.recorder_state import (
    CONFIG_CHANGED_TOOL,
    COVERAGE_WINDOW_CLOSE_TOOL,
    COVERAGE_WINDOW_OPEN_TOOL,
    EXPORT_CONFIGURED_TOOL,
    MARKER_TOOLS,
    PRIVACY_MODE_CHANGED_TOOL,
    RECORDER_INSTALLED_TOOL,
    RECORDER_UNINSTALLED_TOOL,
    RETENTION_CHANGED_TOOL,
    close_coverage_window,
    coverage_windows,
    last_state,
    open_coverage_window,
    reconcile_config,
    record_config_change,
    record_export_configured,
    record_privacy_mode_changed,
    record_recorder_installed,
    record_recorder_uninstalled,
    record_retention_changed,
)
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith("AGENTWATCH_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path / "store"))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return tmp_path


def _store(tmp_path: Path) -> RecordStore:
    return RecordStore(tmp_path / "records.jsonl")


def _markers(store: RecordStore) -> list[str]:
    return [r.tool.name for r in store.records() if r.tool.name in MARKER_TOOLS]


def test_install_and_uninstall_append_markers(tmp_path: Path) -> None:
    store = _store(tmp_path)

    installed = record_recorder_installed(store, scope="project", harness="claude-code", now=START)
    uninstalled = record_recorder_uninstalled(
        store, scope="project", harness="claude-code", now=START + timedelta(minutes=1)
    )

    assert installed.seq is not None
    assert uninstalled.seq is not None
    assert _markers(store) == [RECORDER_INSTALLED_TOOL, RECORDER_UNINSTALLED_TOOL]
    assert store.verify().ok


def test_identical_install_is_coalesced(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record_recorder_installed(store, scope="project", harness="claude-code", now=START)

    again = record_recorder_installed(store, scope="project", harness="claude-code", now=START)

    assert again.coalesced is True
    assert again.seq is None
    assert _markers(store) == [RECORDER_INSTALLED_TOOL]


def test_privacy_downgrade_appends_exactly_one_marker(tmp_path: Path) -> None:
    store = _store(tmp_path)

    first = record_privacy_mode_changed(store, old="full", new="metadata-only", now=START)
    again = record_privacy_mode_changed(store, old="full", new="metadata-only", now=START)

    assert first.seq is not None
    assert again.coalesced is True
    assert _markers(store) == [PRIVACY_MODE_CHANGED_TOOL]


def test_retention_and_export_markers(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record_privacy_mode_changed(store, old=None, new="metadata-only", now=START)
    record_retention_changed(store, old=None, new=30, now=START)
    record_export_configured(store, enabled=False, fmt="otel-genai", now=START)

    assert _markers(store) == [
        PRIVACY_MODE_CHANGED_TOOL,
        RETENTION_CHANGED_TOOL,
        EXPORT_CONFIGURED_TOOL,
    ]
    state = last_state(store)
    assert state.privacy_mode == "metadata-only"
    assert state.retention_days == 30
    assert state.export_enabled is False
    assert state.export_format == "otel-genai"


def test_config_changed_masks_a_secret_value(tmp_path: Path) -> None:
    store = _store(tmp_path)

    record_config_change(store, key="export.otlp_endpoint", new="sk-LEAK-abcdefgh")

    arguments = store.records()[0].tool.arguments
    assert arguments is not None
    assert arguments["key"] == "export.otlp_endpoint"
    assert "sk-LEAK-abcdefgh" not in arguments["new"]
    assert "<REDACTED:api-key>" in arguments["new"]
    assert "sk-LEAK-abcdefgh" not in store.path.read_text(encoding="utf-8")


def test_config_changed_records_old_unknown(tmp_path: Path) -> None:
    store = _store(tmp_path)

    record_config_change(store, key="log.level", new="debug")

    assert store.records()[0].tool.arguments == {
        "key": "log.level",
        "old": "unknown",
        "new": "debug",
    }


def test_config_changed_coalesces_the_same_key(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record_config_change(store, key="log.level", new="debug", old="info", now=START)

    again = record_config_change(store, key="log.level", new="debug", old="info", now=START)

    assert again.coalesced is True
    assert _markers(store) == [CONFIG_CHANGED_TOOL]


def test_export_configured_coalesces_and_omits_endpoint(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record_export_configured(store, enabled=True, fmt="otel-genai", now=START)

    again = record_export_configured(store, enabled=True, fmt="otel-genai", now=START)

    assert again.coalesced is True
    arguments = store.records()[0].tool.arguments
    assert arguments == {"enabled": True, "format": "otel-genai"}


def test_coverage_window_pairs_open_close(tmp_path: Path) -> None:
    store = _store(tmp_path)

    opened = open_coverage_window(store, reason="init:project", now=START)
    assert opened.seq is not None
    windows = coverage_windows(store)
    assert len(windows) == 1
    assert windows[0].active is True

    closed = close_coverage_window(
        store, reason="uninstall:project", now=START + timedelta(hours=1)
    )
    assert closed.seq is not None
    windows = coverage_windows(store)
    assert windows[0].active is False
    assert windows[0].closed_at == START + timedelta(hours=1)


def test_unclosed_window_is_open_ended(tmp_path: Path) -> None:
    store = _store(tmp_path)
    open_coverage_window(store, now=START)

    windows = coverage_windows(store)

    assert windows[-1].active is True
    assert windows[-1].close_seq is None


def test_double_open_and_double_close_are_coalesced(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = open_coverage_window(store, now=START)
    second = open_coverage_window(store, now=START)
    assert first.seq is not None
    assert second.coalesced is True
    close_coverage_window(store, now=START)
    extra_close = close_coverage_window(store, now=START)
    assert extra_close.coalesced is True
    assert _markers(store) == [COVERAGE_WINDOW_OPEN_TOOL, COVERAGE_WINDOW_CLOSE_TOOL]


def test_reconcile_config_records_changes_and_coalesces(tmp_path: Path) -> None:
    store = _store(tmp_path)
    cfg = load_config(paths=[], env={})

    first = reconcile_config(store, cfg, now=START)
    assert {report.tool for report in first} == {
        PRIVACY_MODE_CHANGED_TOOL,
        RETENTION_CHANGED_TOOL,
        EXPORT_CONFIGURED_TOOL,
    }
    assert all(report.seq is not None for report in first)

    again = reconcile_config(store, cfg, now=START)
    assert all(report.coalesced for report in again)
    assert _markers(store) == [
        PRIVACY_MODE_CHANGED_TOOL,
        RETENTION_CHANGED_TOOL,
        EXPORT_CONFIGURED_TOOL,
    ]


def test_cli_init_and_uninstall_append_markers_and_window(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["init", "--no-daemon"])
    assert rc == 0
    capsys.readouterr()

    store = RecordStore(isolated / "store" / "records.jsonl")
    markers = _markers(store)
    assert RECORDER_INSTALLED_TOOL in markers
    assert COVERAGE_WINDOW_OPEN_TOOL in markers
    assert coverage_windows(store)[-1].active is True

    rc = main(["uninstall"])
    assert rc == 0
    capsys.readouterr()

    store = RecordStore(isolated / "store" / "records.jsonl")
    assert RECORDER_UNINSTALLED_TOOL in _markers(store)
    assert coverage_windows(store)[-1].active is False
    assert store.verify().ok


def test_cli_reconciles_privacy_downgrade_on_reinit(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["init", "--no-daemon"]) == 0
    store = RecordStore(isolated / "store" / "records.jsonl")
    assert last_state(store).privacy_mode == "metadata-only"

    # A hand-edited config that downgrades privacy is surfaced on the next run.
    config_dir = isolated / ".agentwatch"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "config.toml").write_text(
        '[privacy]\nmode = "metadata-only"\n\n[store]\nretention_days = 7\n', encoding="utf-8"
    )
    assert main(["init", "--no-daemon"]) == 0
    capsys.readouterr()

    store = RecordStore(isolated / "store" / "records.jsonl")
    assert last_state(store).retention_days == 7
