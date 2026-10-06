"""MCP proxy fault-injection tests (M27 27.T, #377).

The surface expansion multiplies attacker-reachable parsing. These prove the
fail-closed boundaries: an unknown method is rejected with its name and
quarantined by the daemon (harness-drift, S19); closed-by-spec methods are
rejected; malformed frames are contained, never fatal; the proxy relays an
unknown method without recording it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from agentwatch import hook, mcp_proxy
from agentwatch.adapters import mcp_proxy as adapter
from agentwatch.daemon import Daemon
from agentwatch.store import RecordStore


def _frame(method: str) -> dict[str, Any]:
    return {
        "phase": "mcp",
        "harness": "mcp-proxy",
        "event": {
            "server": "github",
            "session_id": "s-1",
            "direction": "request",
            "rpc": {"jsonrpc": "2.0", "id": 7, "method": method, "params": {}},
            "timestamp": "2026-01-02T03:04:05+00:00",
        },
    }


def test_adapter_rejects_an_unknown_method_and_names_it() -> None:
    with pytest.raises(adapter.McpProxyAdapterError) as excinfo:
        adapter.normalize(_frame("resources/subscribe"))

    assert "resources/subscribe" in str(excinfo.value)


def test_closed_by_spec_method_is_rejected() -> None:
    # Roots/Sampling/Logging are retired by the 2026-07-28 spec (SEP-2577).
    assert "mcp-sampling" in adapter.DOCUMENTED_GAPS
    with pytest.raises(adapter.McpProxyAdapterError):
        adapter.normalize(_frame("sampling/createMessage"))


def test_daemon_quarantines_an_unknown_method(tmp_path: Path) -> None:
    daemon = Daemon(
        socket_path=tmp_path / "d.sock",
        store=RecordStore(tmp_path / "records.jsonl"),
        records_path=tmp_path / "records.jsonl",
    )

    written = daemon.handle_message(_frame("resources/subscribe"))

    assert written == []
    assert daemon.store.records() == []
    assert (tmp_path / "quarantine.jsonl").exists()


def test_recorder_relays_but_does_not_record_an_unknown_method(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []

    def _send(message: dict[str, Any], **_: Any) -> bool:
        sent.append(message)
        return True

    monkeypatch.setattr(hook, "send", _send)
    recorder = mcp_proxy.Recorder("github", "s-1")

    recorder.observe_from_harness(_frame("resources/subscribe")["event"]["rpc"])

    assert sent == []


def test_malformed_json_is_contained() -> None:
    assert mcp_proxy._parse(b"{not-json") is None
    # And the recorder ignores a malformed (None) parse rather than crashing.
    mcp_proxy.Recorder("github", "s-1").observe_from_harness(None)
