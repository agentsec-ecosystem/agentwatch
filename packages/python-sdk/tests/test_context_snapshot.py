"""Session-start environment snapshot tests (M19 S16/S29, #257/#258)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agentwatch.adapters import claude_code
from agentwatch.context_snapshot import (
    CONTEXT_CI,
    CONTEXT_HEADLESS,
    CONTEXT_INTERACTIVE,
    VCS_GIT,
    VCS_NONE,
    VCS_UNAVAILABLE,
    classify_context,
    environment_snapshot,
    filter_snapshot,
    git_snapshot,
)


def _run(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
    )


def _git_repo(path: Path) -> Path:
    path.mkdir()
    _run(path, "init", "-q")
    _run(path, "config", "user.email", "t@example.com")
    _run(path, "config", "user.name", "Tester")
    (path / "file.txt").write_text("hello", encoding="utf-8")
    _run(path, "add", "file.txt")
    _run(path, "commit", "-q", "-m", "init")
    return path


def test_classify_context_prefers_ci_then_tty() -> None:
    assert classify_context({"GITHUB_ACTIONS": "1"}, tty=True) == CONTEXT_CI
    assert classify_context({}, tty=False) == CONTEXT_HEADLESS
    assert classify_context({}, tty=True) == CONTEXT_INTERACTIVE


def test_git_snapshot_records_revision_and_dirty(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "repo")

    clean = git_snapshot(repo)

    assert clean["vcs"] == VCS_GIT
    assert len(clean["commit"]) == 40
    assert clean["branch"] == "master" or clean["branch"] == "main"
    assert clean["dirty"] is False

    (repo / "file.txt").write_text("changed", encoding="utf-8")
    assert git_snapshot(repo)["dirty"] is True


def test_git_snapshot_non_git_is_none(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    assert git_snapshot(plain) == {"vcs": VCS_NONE}


def test_git_snapshot_missing_dir_is_unavailable(tmp_path: Path) -> None:
    assert git_snapshot(tmp_path / "missing") == {"vcs": VCS_UNAVAILABLE}
    assert git_snapshot(None) == {"vcs": VCS_UNAVAILABLE}


def test_git_snapshot_failure_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(subprocess, "run", boom)

    assert git_snapshot(tmp_path) == {"vcs": VCS_UNAVAILABLE}


def test_environment_snapshot_is_metadata_only(tmp_path: Path) -> None:
    snapshot = environment_snapshot(str(tmp_path), env={"CI": "true"}, tty=False)

    assert snapshot["vcs"] == {"vcs": VCS_NONE}
    assert snapshot["harness"]["name"] == "claude-code"
    assert snapshot["context"] == CONTEXT_CI
    assert "principal" in snapshot
    assert snapshot["os"]["arch"]
    # No env-var value leaks anywhere in the snapshot.
    assert "true" not in str(snapshot.get("context"))


def test_filter_snapshot_drops_principal() -> None:
    snapshot = environment_snapshot(env={}, tty=True)
    assert "principal" in snapshot

    filtered = filter_snapshot(snapshot, include_principal=False)

    assert "principal" not in filtered
    assert filtered["context"] == CONTEXT_INTERACTIVE


def test_adapter_stores_environment_on_session_start() -> None:
    message = {
        "phase": "session-start",
        "harness": "claude-code",
        "event": {
            "session_id": "s1",
            "timestamp": "2026-01-02T03:04:05+00:00",
            "reason": "startup",
            "environment": environment_snapshot(env={}, tty=True),
        },
    }

    (record,) = claude_code.normalize(message)

    assert record.environment is not None
    assert record.environment["context"] == CONTEXT_INTERACTIVE
    assert record.host


def test_adapter_drops_principal_when_disabled() -> None:
    message = {
        "phase": "session-start",
        "harness": "claude-code",
        "event": {
            "session_id": "s1",
            "timestamp": "2026-01-02T03:04:05+00:00",
            "environment": environment_snapshot(env={"CI": "1"}, tty=False),
        },
    }

    (record,) = claude_code.normalize(message, include_principal=False)

    assert record.environment is not None
    assert "principal" not in record.environment
    assert record.host is None


def test_adapter_ignores_unknown_environment_keys() -> None:
    message = {
        "phase": "session-start",
        "harness": "claude-code",
        "event": {
            "session_id": "s1",
            "timestamp": "2026-01-02T03:04:05+00:00",
            "environment": {
                "vcs": {"vcs": "git", "commit": "abc", "secret": "SHOULD_NOT_STORE"},
                "context": "interactive",
                "evil": {"value": "drop me"},
            },
        },
    }

    (record,) = claude_code.normalize(message)

    assert record.environment is not None
    assert "evil" not in record.environment
    assert "SHOULD_NOT_STORE" not in str(record.environment)
