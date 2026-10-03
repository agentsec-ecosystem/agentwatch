"""Tests for the agentwatch CLI (issue #11).

Covers the M1 acceptance ("``agentwatch --help`` lists commands"), the fail-closed
configuration path (F7), and the milestone-deferred subcommands that must not
silently succeed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.cli import main
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

ALL_COMMANDS = [
    "init",
    "status",
    "sessions",
    "replay",
    "export",
    "verify-store",
    "migrate",
    "uninstall",
]

DEFERRED = ["migrate"]


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run from a temp dir with no user/project config or AGENTWATCH_* env."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    for key in list(os.environ):
        if key.startswith("AGENTWATCH_"):
            monkeypatch.delenv(key, raising=False)
    return tmp_path


def test_help_lists_every_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for command in ALL_COMMANDS:
        assert command in out


@pytest.mark.parametrize("command", ALL_COMMANDS)
def test_subcommand_help_exits_zero(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        main([command, "--help"])
    assert exc.value.code == 0


def test_unknown_subcommand_is_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["definitely-not-a-command"])
    assert exc.value.code != 0


def test_status_prints_resolved_config(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["status"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "claude-code" in out
    assert "monitor" in out
    assert "~/.local/share/agentwatch" in out
    assert "info" in out


def test_status_honours_cli_override(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["--set", "log.level=debug", "status"])
    assert rc == 0
    assert "debug" in capsys.readouterr().out


def test_status_honours_env_override(
    isolated: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AGENTWATCH_LOG__LEVEL", "warn")
    rc = main(["status"])
    assert rc == 0
    assert "warn" in capsys.readouterr().out


def test_launcher_interpreter_env_does_not_break_status(
    isolated: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AGENTWATCH_PYTHON", "/usr/bin/python3")
    rc = main(["status"])
    assert rc == 0
    assert "claude-code" in capsys.readouterr().out


def test_missing_explicit_config_fails_closed(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["--config", str(isolated / "absent.toml"), "status"])
    assert rc != 0
    assert "configuration error" in capsys.readouterr().err.lower()


def test_config_flag_overrides_env(
    isolated: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg_file = isolated / "explicit.toml"
    cfg_file.write_text("log.level = 'debug'\n", encoding="utf-8")
    monkeypatch.setenv("AGENTWATCH_LOG__LEVEL", "warn")

    rc = main(["--config", str(cfg_file), "status"])

    assert rc == 0
    assert "debug" in capsys.readouterr().out


def test_bad_config_fails_closed(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = isolated / "bad.toml"
    bad.write_text("surprise = true\n", encoding="utf-8")

    rc = main(["--config", str(bad), "status"])

    assert rc != 0
    assert "configuration error" in capsys.readouterr().err.lower()


def test_invalid_override_fails_closed(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["--set", "not.a.real.key=1", "status"])
    assert rc != 0
    assert "configuration error" in capsys.readouterr().err.lower()


@pytest.mark.parametrize("command", DEFERRED)
def test_deferred_subcommands_fail_closed(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main([command])
    assert rc != 0
    assert "not implemented" in capsys.readouterr().err.lower()


def test_replay_deferred_fails_closed(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["replay", "session-123"])
    assert rc != 0
    assert "not implemented" in capsys.readouterr().err.lower()


def test_verify_store_reports_clean_and_tampered(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_path = isolated / "records.jsonl"
    record = AgentRecord(
        session_id="s",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    RecordStore(store_path).append(record)

    assert main(["--set", f"store.path={isolated}", "verify-store"]) == 0
    assert "chain ok" in capsys.readouterr().out

    lines = store_path.read_text(encoding="utf-8").splitlines()
    envelope = json.loads(lines[1])
    envelope["record"]["tool"]["name"] = "Tampered"
    lines[1] = json.dumps(envelope)
    store_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert main(["--set", f"store.path={isolated}", "verify-store"]) == 1
    assert "broken" in capsys.readouterr().err.lower()


def test_export_requires_action(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["export"])
    assert exc.value.code != 0


@pytest.mark.parametrize("module", ["agentwatch", "agentwatch.cli"])
def test_module_entry_point_runs(tmp_path: Path, module: str) -> None:
    """``python -m <module> --help`` works (guards __main__.py)."""
    src = Path(__file__).resolve().parents[1] / "src"
    env = {**os.environ, "PYTHONPATH": str(src)}
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        check=False,
    )
    assert result.returncode == 0
    assert "status" in result.stdout
