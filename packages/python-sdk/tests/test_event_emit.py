"""Ecosystem event ingestion (M5 B2, #171).

A sibling tool (or operator) emits a validated security event over the daemon
socket as ``{"phase": "event", "harness": <emitter>, "event": <SecurityEvent>}``.
The daemon validates with ``validate_event`` (reject-never-coerce), appends a
carrier record, and quarantines invalid events. The CLI path is
``agentwatch event emit <type>``.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from agentwatch import hook
from agentwatch.cli import main
from agentwatch.daemon import (
    DEFAULT_EVENT_SESSION,
    EXTERNAL_EVENT_TOOL,
    Daemon,
)
from agentwatch.records import AgentRecord, SecurityEventType
from agentwatch.store import RecordStore

EVENT = {
    "event_version": "0.1.0",
    "type": SecurityEventType.POLICY_FIRED.value,
    "emitted_at": "2026-01-02T03:04:05+00:00",
    "reason": "rate limit",
    "policy_id": "p-1",
    "tool": "Bash",
    "evidence": {"policy_id": "p-1"},
}


@pytest.fixture
def short_dir() -> Iterator[Path]:
    # AF_UNIX paths are length-limited; keep the socket directory short.
    directory = Path(tempfile.mkdtemp(prefix="awe-", dir="/tmp"))
    yield directory
    shutil.rmtree(directory, ignore_errors=True)


def _started(short_dir: Path) -> tuple[Daemon, Path, Path]:
    socket_path = short_dir / "d.sock"
    records_path = short_dir / "records.jsonl"
    daemon = Daemon(socket_path=str(socket_path), records_path=records_path)
    daemon.start()
    return daemon, socket_path, records_path


def _frame(emitter: str = "agentpolicy", *, session_id: str | None = "sess-1") -> dict[str, Any]:
    message = {
        "phase": "event",
        "harness": emitter,
        "event": dict(EVENT),
    }
    if session_id is not None:
        message["session_id"] = session_id
    return message


def _wait_records(daemon: Daemon, count: int, timeout: float = 3.0) -> list[AgentRecord]:
    deadline = time.time() + timeout
    records = daemon.store.records()
    while len(records) < count and time.time() < deadline:
        time.sleep(0.02)
        records = daemon.store.records()
    return records


def test_event_phase_appends_a_carrier_record(short_dir: Path) -> None:
    daemon, socket_path, records_path = _started(short_dir)
    try:
        assert hook.send(_frame(), socket_path=str(socket_path))
        records = _wait_records(daemon, 1)
    finally:
        daemon.stop()

    assert len(records) == 1
    record = records[0]
    assert record.tool.name == EXTERNAL_EVENT_TOOL
    assert record.outcome.value == "ok"
    assert record.session_id == "sess-1"
    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.POLICY_FIRED
    assert record.security_event.emitter == "agentpolicy"
    assert RecordStore(records_path).verify().ok is True


def test_event_for_absent_session_uses_external(short_dir: Path) -> None:
    daemon, _, _ = _started(short_dir)
    try:
        daemon.handle_message(_frame(session_id=None))
        records = daemon.store.records()
    finally:
        daemon.stop()

    assert records[0].session_id == DEFAULT_EVENT_SESSION


def test_event_provenance_is_preserved_per_emitter(short_dir: Path) -> None:
    daemon, _, _ = _started(short_dir)
    try:
        daemon.handle_message(_frame("agentpolicy"))
        daemon.handle_message(_frame("agentkeys", session_id="sess-2"))
        emitters = {record.security_event.emitter for record in daemon.store.records()}  # type: ignore[union-attr]
    finally:
        daemon.stop()

    assert emitters == {"agentpolicy", "agentkeys"}


def test_invalid_event_is_quarantined_and_names_the_field(short_dir: Path) -> None:
    daemon, socket_path, _ = _started(short_dir)
    try:
        bad = _frame()
        bad["event"] = {**EVENT, "emitted_at": "not-a-date"}
        assert hook.send(bad, socket_path=str(socket_path))
        # A valid event afterwards proves the daemon survived and nothing was written.
        assert hook.send(_frame("agentpolicy", session_id="after"), socket_path=str(socket_path))
        records = _wait_records(daemon, 1)
        entries = daemon.quarantine.entries()
    finally:
        daemon.stop()

    assert [record.session_id for record in records] == ["after"]
    assert entries
    assert any("emitted_at" in entry["reason"] for entry in entries)


def test_unknown_event_key_is_quarantined(short_dir: Path) -> None:
    daemon, _, _ = _started(short_dir)
    try:
        daemon.handle_message(
            {"phase": "event", "harness": "agentpolicy", "event": {**EVENT, "surprise": True}}
        )
        records = daemon.store.records()
        entries = daemon.quarantine.entries()
    finally:
        daemon.stop()

    assert records == []
    assert any("surprise" in entry["reason"] for entry in entries)


def test_missing_emitter_is_quarantined(short_dir: Path) -> None:
    daemon, _, _ = _started(short_dir)
    try:
        daemon.handle_message({"phase": "event", "event": dict(EVENT)})
        records = daemon.store.records()
        entries = daemon.quarantine.entries()
    finally:
        daemon.stop()

    assert records == []
    assert any("harness" in entry["reason"] for entry in entries)


def test_duplicate_event_is_deduped(short_dir: Path) -> None:
    daemon, _, _ = _started(short_dir)
    try:
        first = daemon.handle_message(_frame())
        second = daemon.handle_message(_frame())
        records = daemon.store.records()
    finally:
        daemon.stop()

    assert len(first) == 1
    assert second == []
    assert len(records) == 1


def test_distinct_events_are_not_deduped(short_dir: Path) -> None:
    daemon, _, _ = _started(short_dir)
    try:
        daemon.handle_message(_frame())
        other = _frame()
        other["event"] = {**EVENT, "type": SecurityEventType.HALTED.value}
        daemon.handle_message(other)
        records = daemon.store.records()
    finally:
        daemon.stop()

    assert len(records) == 2


def test_event_emit_cli_sends_a_validated_frame(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sent: list[dict[str, Any]] = []

    def fake_send(message: dict[str, Any], *, socket_path: str | None = None) -> bool:
        sent.append(message)
        return True

    monkeypatch.setattr("agentwatch.hook.send", fake_send)

    rc = main(
        [
            "event",
            "emit",
            "policy-fired",
            "--session-id",
            "sess-1",
            "--tool",
            "Bash",
            "--reason",
            "rate limit",
            "--evidence",
            '{"policy_id": "p-1"}',
        ]
    )

    assert rc == 0
    assert len(sent) == 1
    message = sent[0]
    assert message["phase"] == "event"
    assert message["harness"] == "agentwatch"
    assert message["session_id"] == "sess-1"
    assert message["event"]["type"] == "policy-fired"
    assert message["event"]["tool"] == "Bash"
    assert message["event"]["evidence"] == {"policy_id": "p-1"}
    assert capsys.readouterr().out.strip()


def test_event_emit_cli_rejects_bad_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agentwatch.hook.send", lambda *a, **k: True)
    rc = main(["event", "emit", "policy-fired", "--evidence", "not json"])
    assert rc != 0


def test_event_emit_cli_fails_closed_when_daemon_is_down(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("agentwatch.hook.send", lambda *a, **k: False)
    rc = main(["event", "emit", "policy-fired"])
    assert rc != 0
    assert capsys.readouterr().err.strip()


def test_emitted_event_shows_up_in_sessions(
    short_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    daemon, socket_path, records_path = _started(short_dir)
    try:
        assert hook.send(_frame("agentpolicy", session_id="sess-1"), socket_path=str(socket_path))
        _wait_records(daemon, 1)
    finally:
        daemon.stop()

    monkeypatch.chdir(short_dir)
    rc = main(["--set", f"store.path={short_dir}", "sessions"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "sess-1" in out
    assert json.loads((records_path).read_text(encoding="utf-8").splitlines()[1])  # chain present
