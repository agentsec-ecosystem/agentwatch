"""Anti-forensics suite: treat the recorder as an attack target (M16 S30, #242).

agentwatch observes an agent that runs on the same machine, as the same user, with
shell access. This suite *tries* the tamper scenarios — kill the daemon, truncate
the store, strip hooks, exhaust disk, hold the socket, move the store, skew the
clock, replay stale frames — and asserts the documented outcome from
``docs/design/recorder-attack-matrix.md``: what is detected, which command shows
it, and what is only *neither* (with its compensating control).
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from agentwatch import hook
from agentwatch.cli.main import main
from agentwatch.coverage import build_coverage
from agentwatch.daemon import Daemon
from agentwatch.health import HealthSnapshot
from agentwatch.install import hooks_installed, install_hooks, resolve_hook_command, uninstall_hooks
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore, StoreFullError

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(*, session: str = "s1", span: str = "sp1", at: datetime | None = None) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent-1"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=at or START,
        span_id=span,
        step_type=None,
    )


def _pre(span: str = "p1", *, ts: str | None = None) -> dict[str, Any]:
    return {
        "phase": "pre",
        "harness": "claude-code",
        "event": {
            "session_id": "s1",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_use_id": span,
            "timestamp": ts or START.isoformat(),
        },
    }


def _daemon(tmp_path: Path, *, store: RecordStore | None = None) -> tuple[Daemon, HealthSnapshot]:
    health = HealthSnapshot(store_path=tmp_path / "records.jsonl")
    daemon = Daemon(
        socket_path=tmp_path / "d.sock",
        store=store or RecordStore(tmp_path / "records.jsonl"),
        records_path=tmp_path / "records.jsonl",
        health=health,
    )
    return daemon, health


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


@pytest.fixture
def short_dir() -> Iterator[Path]:
    directory = Path(tempfile.mkdtemp(prefix="awa-", dir="/tmp"))
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)


# 1. Kill the daemon mid-session -------------------------------------------------


def test_kill_daemon_mid_session_records_a_gap(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record(at=datetime.now(timezone.utc) - timedelta(hours=1)))
    (tmp_path / "daemon.pid").write_text("4242", encoding="utf-8")
    daemon, health = _daemon(tmp_path, store=store)

    daemon._record_gap_if_needed()

    assert "recording-gap" in [r.tool.name for r in store.records()]
    assert health.to_dict()["reason"] == "recording-gap"


# 2. Truncate / append garbage to the store --------------------------------------


def test_store_truncation_or_garbage_is_detected_by_verify(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    with store.path.open("a", encoding="utf-8") as handle:
        handle.write('{"seq": 99, "prev_hash": "x", "hash": "y", "record": ')

    assert RecordStore(store.path).verify().ok is False

    assert main(["--set", f"store.path={tmp_path}", "verify-store"]) != 0


# 3. Strip hooks from settings ---------------------------------------------------


def test_stripped_hooks_are_surfaced_by_status(tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.local.json"
    install_hooks(settings, resolve_hook_command())
    assert hooks_installed(settings) is True

    # The on-box attacker edits the file directly; no chain record is written.
    uninstall_hooks(settings)

    assert hooks_installed(settings) is False


# 4. Exhaust disk (trip the size cap) -------------------------------------------


def test_exhausted_disk_fails_closed(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl", max_size_mb=0)
    daemon, health = _daemon(tmp_path, store=store)

    with pytest.raises(StoreFullError):
        store.append(_record())
    assert daemon._append(_record()) is None
    assert health.to_dict()["state"] == "stopped"


# 5. Hold the socket -------------------------------------------------------------


def test_held_socket_refuses_a_second_daemon(short_dir: Path) -> None:
    first, _ = _daemon(short_dir)
    first.start()
    try:
        second, _ = _daemon(short_dir, store=RecordStore(short_dir / "records.jsonl"))
        with pytest.raises(RuntimeError):
            second.start()
    finally:
        first.stop()


def test_socket_held_by_an_attacker_spools_instead_of_losing(tmp_path: Path) -> None:
    # Nothing is listening: the event is spooled (F1), never silently lost.
    socket_path = tmp_path / "nobody.sock"
    rc = hook.main(["pre"], stdin=io.StringIO(json.dumps(_pre())), socket_path=str(socket_path))
    assert rc == 0
    assert Path(str(socket_path) + ".spool").exists()


# 6. Move the store --------------------------------------------------------------


def test_moved_store_is_neither_clean_nor_detected_by_the_chain(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record(session="s1", span="sp1"))
    moved = tmp_path / "elsewhere.jsonl"
    store.path.replace(moved)

    # The chain on the old path looks clean-but-empty: the chain alone cannot tell.
    assert RecordStore(tmp_path / "records.jsonl").verify().ok is True
    # S2 coverage is the compensating control: transcript ground truth vs empty store.
    from agentwatch.coverage import TranscriptCoverage

    report = build_coverage(
        RecordStore(tmp_path / "records.jsonl"),
        transcripts={"s1": TranscriptCoverage(session_id="s1", tool_calls=1)},
        transcripts_present=True,
        hooks_installed=True,
    )
    assert report.sessions[0].gaps != ()


# 7. Skew the clock --------------------------------------------------------------


def test_clock_skew_is_flagged(tmp_path: Path) -> None:
    daemon, health = _daemon(tmp_path)
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    daemon.handle_message(_pre(ts=future))

    payload = health.to_dict()
    assert payload["clock_skew_s"] is not None
    assert payload["state"] == "degraded"
    assert payload["reason"] == "clock-skew"


# 8. Replay stale frames ---------------------------------------------------------


def test_stale_frame_replay_is_deduplicated(tmp_path: Path) -> None:
    daemon, _ = _daemon(tmp_path)

    first = daemon.handle_message(_pre())
    second = daemon.handle_message(_pre())

    assert len(first) == 1
    assert second == []
    assert len(daemon.store.records()) == 1


def test_stale_replay_across_restart_is_neither_preventable_nor_detected(
    tmp_path: Path,
) -> None:
    records_path = tmp_path / "records.jsonl"
    first, _ = _daemon(tmp_path, store=RecordStore(records_path))
    first.handle_message(_pre())

    # A restarted daemon has no in-memory dedupe set: the same frame appends again.
    second, _ = _daemon(tmp_path, store=RecordStore(records_path))
    second.handle_message(_pre())

    assert len(RecordStore(records_path).records()) == 2


# The matrix must name the command that evidences each row.
def test_attack_matrix_document_exists() -> None:
    repo = Path(__file__).resolve().parents[3]
    matrix = repo / "docs" / "design" / "recorder-attack-matrix.md"
    text = matrix.read_text(encoding="utf-8")
    for scenario in (
        "Kill the daemon",
        "Truncate",
        "Strip hooks",
        "Exhaust disk",
        "Hold the socket",
        "Move the store",
        "Skew the clock",
        "Replay stale frames",
    ):
        assert scenario in text, f"matrix missing scenario: {scenario}"
    assert "verify-store" in text
    assert "coverage" in text
