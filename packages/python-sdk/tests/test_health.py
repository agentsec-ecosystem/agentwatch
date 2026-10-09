"""Health endpoint + snapshot tests (M5 B1, #170; PRD 13/NFR-12).

The daemon proves it is recording: ``GET /healthz`` returns the PRD 13 field
set, the snapshot derives ``recording``/``degraded``/``stopped`` with a reason,
and the server binds loopback only. Health is best-effort: a busy port must not
stop recording.
"""

from __future__ import annotations

import json
import shutil
import socket
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch import hook
from agentwatch.daemon import Daemon
from agentwatch.health import (
    HealthSnapshot,
    fetch_health,
    local_snapshot,
    start_health_server,
)
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import ChainStatus, RecordStore

_VERSION = "9.9.9"


@pytest.fixture
def short_dir() -> Iterator[Path]:
    # AF_UNIX paths are length-limited; keep the socket directory short.
    directory = Path(tempfile.mkdtemp(prefix="awh-", dir="/tmp"))
    yield directory
    shutil.rmtree(directory, ignore_errors=True)


def _record(name: str = "Bash") -> AgentRecord:
    return AgentRecord(
        session_id="sess-1",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=name),
        outcome=Outcome.OK,
        started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _snapshot(tmp_path: Path) -> HealthSnapshot:
    return HealthSnapshot(
        store_path=tmp_path / "records.jsonl",
        version=_VERSION,
        pid=4321,
        started_at=datetime.now(timezone.utc),
    )


def _get(endpoint: str, path: str = "/healthz") -> tuple[int, object]:
    url = f"http://{endpoint}{path}"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def test_snapshot_exposes_every_nfr12_field(tmp_path: Path) -> None:
    payload = _snapshot(tmp_path).to_dict()

    assert set(payload) == {
        "state",
        "reason",
        "daemon",
        "store",
        "export",
        "redaction",
        "signing",
        "hooks",
        "gaps",
        "drift",
        "clock_skew_s",
    }
    assert set(payload["daemon"]) == {"pid", "uptime_s", "version"}
    assert set(payload["store"]) == {
        "path",
        "records",
        "size_mb",
        "chain_ok",
        "durability",
        "last_append_at",
    }
    assert set(payload["export"]) == {"enabled", "endpoint", "last_success_at", "last_error"}
    assert set(payload["redaction"]) == {"mode", "self_test_passing"}
    assert isinstance(payload["gaps"], list)
    assert isinstance(payload["drift"], list)
    assert payload["daemon"]["pid"] == 4321
    assert payload["daemon"]["version"] == _VERSION
    assert isinstance(payload["daemon"]["uptime_s"], float)
    assert isinstance(payload["store"]["records"], int)
    assert isinstance(payload["store"]["size_mb"], float)
    assert isinstance(payload["store"]["chain_ok"], bool)
    assert isinstance(payload["redaction"]["self_test_passing"], bool)


def test_state_is_degraded_until_a_hook_fires(tmp_path: Path) -> None:
    snapshot = HealthSnapshot(
        store_path=tmp_path / "records.jsonl",
        version=_VERSION,
        hooks_installed=True,
    )

    payload = snapshot.to_dict()

    assert payload["state"] == "degraded"
    assert payload["reason"] == "hooks-never-fired"
    assert payload["hooks"]["claude-code"]["installed"] is True
    assert payload["hooks"]["claude-code"]["last_fire_at"] is None


def test_state_recording_when_hooks_fire(tmp_path: Path) -> None:
    snapshot = HealthSnapshot(
        store_path=tmp_path / "records.jsonl",
        version=_VERSION,
        hooks_installed=True,
    )

    snapshot.note_hook_fire("claude-code")

    payload = snapshot.to_dict()
    assert payload["state"] == "recording"
    assert payload["reason"] is None
    assert payload["hooks"]["claude-code"]["last_fire_at"] is not None


def test_state_degrades_on_self_test_failure(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    snapshot.note_hook_fire("claude-code")

    snapshot.set_self_test(passing=False)

    payload = snapshot.to_dict()
    assert payload["state"] == "degraded"
    assert payload["reason"] == "redaction-self-test-failed"
    assert payload["redaction"]["self_test_passing"] is False


def test_state_degrades_on_export_error(tmp_path: Path) -> None:
    snapshot = HealthSnapshot(
        store_path=tmp_path / "records.jsonl",
        version=_VERSION,
        export_enabled=True,
        export_endpoint="http://collector:4317",
    )
    snapshot.note_hook_fire("claude-code")
    snapshot.set_export_error("connection refused")

    payload = snapshot.to_dict()
    assert payload["state"] == "degraded"
    assert payload["reason"] == "export-error"
    assert payload["export"]["last_error"] == "connection refused"
    assert payload["export"]["enabled"] is True

    snapshot.set_export_success()
    assert snapshot.to_dict()["export"]["last_success_at"] is not None
    assert snapshot.to_dict()["state"] == "recording"


def test_state_stopped_on_broken_chain(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)

    snapshot.set_chain(ChainStatus(ok=False, checked=3, broken_at=2))

    payload = snapshot.to_dict()
    assert payload["state"] == "stopped"
    assert payload["reason"] is not None
    assert "2" in payload["reason"]
    assert payload["store"]["chain_ok"] is False


def test_state_stopped_on_store_full(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)

    snapshot.set_stopped("store full")

    payload = snapshot.to_dict()
    assert payload["state"] == "stopped"
    assert payload["reason"] == "store full"


def test_gap_events_are_surfaced_and_degrade(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    snapshot.note_hook_fire("claude-code")
    snapshot.note_gap({"reason": "daemon-restart", "at": "2026-01-02T03:00:00+00:00"})

    payload = snapshot.to_dict()
    assert payload["state"] == "degraded"
    assert payload["reason"] == "recording-gap"
    assert payload["gaps"][0]["reason"] == "daemon-restart"


def test_record_appended_updates_counts(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())

    snapshot.record_appended(_record(), size_bytes=store.size_bytes())

    payload = snapshot.to_dict()
    assert payload["store"]["records"] == 1
    assert payload["store"]["size_mb"] >= 0.0
    assert payload["store"]["last_append_at"] is not None


def test_healthz_serves_json_on_loopback(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    server = start_health_server(snapshot, "127.0.0.1:0")
    assert server is not None
    try:
        host, port = server.address
        assert host == "127.0.0.1"
        status, payload = _get(f"{host}:{port}")
    finally:
        server.stop()

    assert status == 200
    assert isinstance(payload, dict)
    assert payload["state"] in {"recording", "degraded", "stopped"}
    assert payload["daemon"]["version"] == _VERSION


def test_healthz_unknown_path_is_404(tmp_path: Path) -> None:
    server = start_health_server(_snapshot(tmp_path), "127.0.0.1:0")
    assert server is not None
    try:
        host, port = server.address
        status, _ = _get(f"{host}:{port}", "/nope")
    finally:
        server.stop()

    assert status == 404


def test_non_loopback_config_binds_loopback(tmp_path: Path) -> None:
    server = start_health_server(_snapshot(tmp_path), "0.0.0.0:0")
    assert server is not None
    try:
        assert server.address[0] == "127.0.0.1"
    finally:
        server.stop()


def test_busy_port_is_non_fatal(tmp_path: Path) -> None:
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    occupied.bind(("127.0.0.1", 0))
    occupied.listen(1)
    port = occupied.getsockname()[1]
    try:
        assert start_health_server(_snapshot(tmp_path), f"127.0.0.1:{port}") is None
    finally:
        occupied.close()


def test_local_snapshot_reports_stopped_when_daemon_down(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())

    payload = local_snapshot(store=store, version=_VERSION).to_dict()

    assert payload["state"] == "stopped"
    assert payload["reason"] == "daemon-not-running"
    assert payload["store"]["records"] == 1
    assert payload["store"]["chain_ok"] is True


def test_fetch_health_returns_none_when_unreachable() -> None:
    assert fetch_health("127.0.0.1:1") is None


def test_daemon_healthz_reflects_activity(short_dir: Path) -> None:
    daemon = Daemon(
        socket_path=str(short_dir / "d.sock"),
        records_path=short_dir / "records.jsonl",
        health_endpoint="127.0.0.1:0",
    )
    daemon.start()
    try:
        address = daemon.health_address
        assert address is not None
        endpoint = f"{address[0]}:{address[1]}"
        assert hook.send(
            {
                "phase": "pre",
                "harness": "claude-code",
                "event": {
                    "session_id": "sess-1",
                    "tool_name": "Bash",
                    "tool_use_id": "c1",
                    "timestamp": "2026-01-02T03:04:05+00:00",
                },
            },
            socket_path=str(short_dir / "d.sock"),
        )
        deadline = 0.0
        payload = fetch_health(endpoint)
        while payload is not None and payload["store"]["records"] < 1 and deadline < 3.0:
            time.sleep(0.02)
            deadline += 0.02
            payload = fetch_health(endpoint)
    finally:
        daemon.stop()

    assert payload is not None
    assert payload["state"] == "recording"
    assert payload["store"]["records"] == 1
    assert payload["hooks"]["claude-code"]["last_fire_at"] is not None
    assert payload["daemon"]["pid"] > 0
    assert payload["daemon"]["version"]


def test_daemon_store_full_flips_state_to_stopped(short_dir: Path) -> None:
    store = RecordStore(short_dir / "records.jsonl", max_size_mb=0)
    daemon = Daemon(
        socket_path=str(short_dir / "d.sock"),
        records_path=short_dir / "records.jsonl",
        store=store,
        health_endpoint="127.0.0.1:0",
    )
    daemon.start()
    try:
        address = daemon.health_address
        assert address is not None
        hook.send(
            {
                "phase": "pre",
                "harness": "claude-code",
                "event": {"session_id": "s", "tool_name": "Bash", "tool_use_id": "c1"},
            },
            socket_path=str(short_dir / "d.sock"),
        )
        deadline = time.time() + 3.0
        payload = daemon.health.to_dict()
        while payload["state"] != "stopped" and time.time() < deadline:
            time.sleep(0.02)
            payload = daemon.health.to_dict()
    finally:
        daemon.stop()

    assert payload["state"] == "stopped"
    assert payload["reason"] is not None
    assert payload["store"]["chain_ok"] is True
