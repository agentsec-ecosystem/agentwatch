"""Security-event forwarding sink tests (M20 S10, #263)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from agentwatch.configuration import ConfigError, load_config
from agentwatch.daemon import Daemon
from agentwatch.sinks import (
    EventForwarder,
    SinkError,
    SyslogSink,
    build_sink,
    event_bytes,
)

TS = "2026-01-02T03:04:05+00:00"
DENIED = {
    "phase": "denied",
    "harness": "claude-code",
    "event": {"session_id": "s1", "tool_name": "Bash", "timestamp": TS, "reason": "no"},
}
BENIGN = {
    "phase": "pre",
    "harness": "claude-code",
    "event": {"session_id": "s1", "tool_name": "Read", "tool_use_id": "c1", "timestamp": TS},
}


def test_file_sink_receives_events(tmp_path: Path) -> None:
    target = "file://" + str(tmp_path / "events.ndjson")
    forwarder = EventForwarder([target])

    forwarder.forward({"type": "denied", "tool": "Bash"})

    assert forwarder.state.delivered == 1
    assert forwarder.state.degraded is False
    text = (tmp_path / "events.ndjson").read_text(encoding="utf-8")
    assert json.loads(text)["type"] == "denied"


def test_webhook_failure_is_degraded_and_bounded(tmp_path: Path) -> None:
    def boom(request: Any, timeout: float) -> Any:
        raise OSError("connection refused")

    forwarder = EventForwarder(["https://example.invalid/hook"], webhook_opener=boom)

    forwarder.forward({"type": "halted"})

    assert forwarder.state.degraded is True
    assert forwarder.state.queued == 1
    assert "webhook" in (forwarder.state.last_error or "")


def test_webhook_success(tmp_path: Path) -> None:
    seen: list[bytes] = []

    def ok(request: Any, timeout: float) -> Any:
        seen.append(request.data)
        return object()

    forwarder = EventForwarder(["https://example.invalid/hook"], webhook_opener=ok)
    forwarder.forward({"type": "halted"})

    assert forwarder.state.delivered == 1
    assert json.loads(seen[0])["type"] == "halted"


def test_syslog_sink_uses_handler() -> None:
    records: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    sink = SyslogSink(handler=Capture())
    sink.deliver({"type": "denied"})

    assert any("denied" in line for line in records)


def test_build_sink_rejects_unknown_target() -> None:
    with pytest.raises(SinkError):
        build_sink("gopher://example")


def test_event_bytes_is_one_line() -> None:
    assert event_bytes({"b": 1, "a": 2}) == b'{"a": 2, "b": 1}\n'


# --------------------------------------------------------------------------- config gate


def test_sinks_enabled_requires_targets() -> None:
    with pytest.raises(ConfigError):
        load_config(cli_overrides={"sinks.enabled": True})


def test_sinks_enabled_requires_self_test() -> None:
    with pytest.raises(ConfigError):
        load_config(
            cli_overrides={
                "sinks.enabled": True,
                "sinks.targets": ["file:///tmp/e.ndjson"],
                "redaction.self_test": "disabled",
            }
        )


def test_sinks_config_valid() -> None:
    cfg = load_config(
        cli_overrides={"sinks.enabled": True, "sinks.targets": ["file:///tmp/e.ndjson"]}
    )
    assert cfg.sinks.enabled is True
    assert cfg.sinks.targets == ("file:///tmp/e.ndjson",)
    assert any("sinks.enabled" in w for w in cfg.warnings)


# --------------------------------------------------------------------------- daemon


def test_daemon_forwards_events_only(tmp_path: Path) -> None:
    events_path = tmp_path / "events.ndjson"
    daemon = Daemon(
        socket_path=str(tmp_path / "d.sock"),
        records_path=tmp_path / "records.jsonl",
        sink_targets=("file://" + str(events_path),),
    )

    daemon.handle_message(DENIED)
    daemon.handle_message(BENIGN)

    lines = [line for line in events_path.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 1
    assert json.loads(lines[0])["type"] == "denied"
    # The full record is never forwarded.
    assert "privacy_mode" not in lines[0]
