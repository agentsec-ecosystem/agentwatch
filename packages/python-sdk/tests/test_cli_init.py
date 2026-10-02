"""CLI tests for ``agentwatch init`` / ``uninstall`` / ``sessions`` (M3 #159).

``init`` installs hooks into a Claude Code settings file and (unless
``--no-daemon``) starts the local daemon; ``uninstall`` reverses it. These tests
isolate HOME/cwd/store and use ``--no-daemon`` so no process is spawned.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.cli import main
from agentwatch.install import hooks_installed
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run from a temp dir with no user/project config or stray AGENTWATCH_* env."""
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith("AGENTWATCH_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path / "store"))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return tmp_path


def test_init_installs_project_hooks(isolated: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["init", "--no-daemon"])

    assert rc == 0
    settings = isolated / ".claude" / "settings.local.json"
    assert hooks_installed(settings)
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["hooks"]["PreToolUse"][0]["matcher"] == "*"
    assert "installed" in capsys.readouterr().out.lower()


def test_init_user_scope_writes_user_settings(isolated: Path) -> None:
    rc = main(["init", "--no-daemon", "--scope", "user"])

    assert rc == 0
    assert hooks_installed(isolated / "home" / ".claude" / "settings.json")


def test_init_no_daemon_does_not_start_one(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENTWATCH_SOCKET", str(isolated / "d.sock"))

    rc = main(["init", "--no-daemon"])

    assert rc == 0
    from agentwatch.install import is_daemon_alive

    assert is_daemon_alive() is False


def test_uninstall_removes_installed_hooks(isolated: Path) -> None:
    main(["init", "--no-daemon"])

    rc = main(["uninstall"])

    assert rc == 0
    assert hooks_installed(isolated / ".claude" / "settings.local.json") is False


def test_status_reports_hooks_and_daemon(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["status"])
    before = capsys.readouterr().out
    assert "daemon:" in before
    assert "absent" in before

    main(["init", "--no-daemon"])
    main(["status"])
    after = capsys.readouterr().out
    assert "installed" in after


def test_status_reflects_user_scope_hooks(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["init", "--no-daemon", "--scope", "user"])
    capsys.readouterr()  # discard init output

    main(["status"])

    out = capsys.readouterr().out
    assert "hooks: installed (user)" in out


def _write_records(isolated: Path) -> None:
    store = RecordStore(isolated / "store" / "records.jsonl")
    for session_id, tool_name in [("sess-a", "Bash"), ("sess-b", "Read"), ("sess-a", "Edit")]:
        store.append(
            AgentRecord(
                session_id=session_id,
                agent=AgentIdentity(identity="a"),
                tool=ToolCall(name=tool_name),
                outcome=Outcome.OK,
                started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )
        )


def test_sessions_lists_recorded_sessions(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_records(isolated)

    rc = main(["sessions"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "sess-a" in out
    assert "sess-b" in out
    assert "2" in out  # sess-a has two records


def test_sessions_without_records_is_not_an_error(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["sessions"])

    assert rc == 0
    assert "no sessions" in capsys.readouterr().out.lower()
