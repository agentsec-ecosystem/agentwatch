"""Tests for operator additions: preflight, verify-privacy, consent init, completions."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.cli import main
from agentwatch.install import preflight
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)
from agentwatch.store import RecordStore
from agentwatch.verify_privacy import verify_privacy

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith("AGENTWATCH_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return tmp_path


def _record(*, arguments: dict[str, object] | None = None) -> AgentRecord:
    return AgentRecord(
        session_id="s",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name="Bash", arguments=arguments, privacy_mode=RecordPrivacyMode.FULL),
        outcome=Outcome.OK,
        started_at=_T0,
    )


def test_preflight_warns_for_missing_and_untested_versions() -> None:
    assert preflight(None)
    assert preflight("1.0.0")
    assert preflight("2.1.187") == []


def test_verify_privacy_passes_a_clean_store(tmp_path: Path) -> None:
    RecordStore(tmp_path / "records.jsonl").append(_record(arguments=None))

    assert verify_privacy(tmp_path / "records.jsonl").passed is True


def test_verify_privacy_flags_a_stored_secret(tmp_path: Path) -> None:
    RecordStore(tmp_path / "records.jsonl").append(_record(arguments={"cmd": "sk-abcdefgh"}))

    verdict = verify_privacy(tmp_path / "records.jsonl")

    assert verdict.passed is False
    assert any("kinds=api-key" in leak for leak in verdict.leaks)
    assert not any("sk-abcdefgh" in leak for leak in verdict.leaks)  # never echo the value


def test_cli_verify_privacy_exit_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    RecordStore(tmp_path / "records.jsonl").append(_record(arguments={"cmd": "sk-abcdefgh"}))

    rc = main(["--set", f"store.path={tmp_path}", "verify-privacy"])

    assert rc != 0
    assert "leak" in capsys.readouterr().err.lower()


def test_init_dry_run_writes_nothing(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["init", "--no-daemon", "--dry-run"])

    assert rc == 0
    assert "dry-run" in capsys.readouterr().out
    assert not (isolated / ".claude" / "settings.local.json").exists()


def test_completions_script(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["completions", "bash"])

    assert rc == 0
    assert "agentwatch" in capsys.readouterr().out
