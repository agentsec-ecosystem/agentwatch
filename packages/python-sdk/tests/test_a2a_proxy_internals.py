"""A2A proxy engine internals (M29 A2A-1 #364): framing, pairing, spool, CLI."""

from __future__ import annotations

import io
import pathlib
from typing import Any

import pytest

from agentwatch import a2a_proxy, hook


def _capture(monkeypatch: pytest.MonkeyPatch, frames: list[dict[str, Any]]) -> None:
    def _send(message: dict[str, Any], **_: Any) -> bool:
        frames.append(message)
        return True

    monkeypatch.setattr(hook, "send", _send)


def test_parse_routes_parses_and_rejects() -> None:
    assert a2a_proxy.parse_routes(["a=http://x/"]) == {"a": "http://x/"}
    with pytest.raises(ValueError):
        a2a_proxy.parse_routes(["a"])
    with pytest.raises(ValueError):
        a2a_proxy.parse_routes(["a=ftp://x"])


def test_records_from_payload_variants() -> None:
    assert a2a_proxy._records_from_payload({"a": 1}) == [{"a": 1}]
    assert a2a_proxy._records_from_payload([{"a": 1}, 2]) == [{"a": 1}]
    assert a2a_proxy._records_from_payload(5) == []


def test_card_from_body_variants() -> None:
    assert a2a_proxy._card_from_body(b'{"name": "x"}') == {"name": "x"}
    assert a2a_proxy._card_from_body(b'{"jsonrpc": "2.0"}') is None
    assert a2a_proxy._card_from_body(b"not json") is None


def test_is_recordable_request_only_accepts_recordable_methods() -> None:
    assert a2a_proxy.is_recordable_request({"method": "message/send"})
    assert not a2a_proxy.is_recordable_request({"method": "initialize"})
    assert not a2a_proxy.is_recordable_request("not-a-mapping")


def test_recorder_frames_a_tasks_request_with_the_task_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    frames: list[dict[str, Any]] = []
    _capture(monkeypatch, frames)
    recorder = a2a_proxy.Recorder(
        "scheduler", "s-1", socket_path=str(tmp_path / "d.sock"), remote_org="Acme"
    )

    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 8, "method": "tasks/get", "params": {"id": "t-9"}}
    )
    recorder.observe_from_server({"jsonrpc": "2.0", "id": 8, "result": {"kind": "task"}})

    assert frames[0]["event"]["task_id"] == "t-9"
    assert frames[0]["event"]["remote_org"] == "Acme"
    assert frames[1]["event"]["direction"] == "response"


def test_recorder_handles_a_request_without_params(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    frames: list[dict[str, Any]] = []
    _capture(monkeypatch, frames)
    recorder = a2a_proxy.Recorder("scheduler", "s-1", socket_path=str(tmp_path / "d.sock"))

    recorder.observe_from_harness({"jsonrpc": "2.0", "id": 1, "method": "tasks/get"})

    assert frames[0]["event"]["tool_name"] == "tasks/get"


def test_pump_harness_stops_on_a_broken_child_stdin(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    frames: list[dict[str, Any]] = []
    _capture(monkeypatch, frames)
    recorder = a2a_proxy.Recorder("scheduler", "s-1", socket_path=str(tmp_path / "d.sock"))

    class _BadStdin:
        def write(self, data: bytes) -> int:
            raise OSError("closed")

        def flush(self) -> None:
            pass

        def close(self) -> None:
            pass

    payload = b'{"jsonrpc": "2.0", "id": 1, "method": "tasks/get", "params": {"id": "t"}}\n'
    a2a_proxy._pump_harness(
        io.BytesIO(payload), _BadStdin(), recorder  # type: ignore[arg-type]
    )

    assert frames[0]["event"]["tool_name"] == "tasks/get"


def test_recorder_flush_pending_records_an_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    frames: list[dict[str, Any]] = []
    _capture(monkeypatch, frames)
    recorder = a2a_proxy.Recorder("scheduler", "s-1", socket_path=str(tmp_path / "d.sock"))
    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 3, "method": "tasks/get", "params": {"id": "t"}}
    )
    frames.clear()

    recorder.flush_pending("server exited")

    assert frames[0]["event"]["rpc"]["error"]["message"] == "server exited"


def test_recorder_spools_when_the_daemon_is_unreachable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    monkeypatch.setattr(hook, "send", lambda message, **_: False)
    socket_path = str(tmp_path / "d.sock")
    recorder = a2a_proxy.Recorder("scheduler", "s-1", socket_path=socket_path)

    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 1, "method": "tasks/get", "params": {"id": "t"}}
    )

    assert pathlib.Path(socket_path + ".spool").exists()


def test_serve_http_handles_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeServer:
        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            pass

    monkeypatch.setattr(a2a_proxy, "create_http_proxy", lambda *a, **k: _FakeServer())

    assert a2a_proxy.serve_http({"a": "http://x/"}) == 0


def test_main_http_requires_a_route(capsys: pytest.CaptureFixture[str]) -> None:
    assert a2a_proxy.main(["--http"]) == 2
    assert "requires" in capsys.readouterr().err


def test_main_http_rejects_a_malformed_route(capsys: pytest.CaptureFixture[str]) -> None:
    assert a2a_proxy.main(["--http", "--route", "echo"]) == 2
    assert "invalid route" in capsys.readouterr().err


def test_main_http_serves(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_serve(routes: dict[str, str], **kwargs: Any) -> int:
        captured["routes"] = routes
        captured["port"] = kwargs.get("port")
        return 0

    monkeypatch.setattr(a2a_proxy, "serve_http", fake_serve)
    rc = a2a_proxy.main(["--http", "--port", "9999", "--route", "a=http://x/"])

    assert rc == 0
    assert captured == {"routes": {"a": "http://x/"}, "port": 9999}


def test_main_stdio_relays(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run(agent: str, command: list[str], **kwargs: Any) -> int:
        captured["agent"] = agent
        captured["command"] = list(command)
        captured["remote_org"] = kwargs.get("remote_org")
        return 0

    monkeypatch.setattr(a2a_proxy, "run_stdio", fake_run)
    rc = a2a_proxy.main(["--agent", "a", "--remote-org", "Acme", "--", "cmd", "arg"])

    assert rc == 0
    assert captured == {"agent": "a", "command": ["cmd", "arg"], "remote_org": "Acme"}


def test_main_stdio_requires_a_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert a2a_proxy.main(["--agent", "a"]) == 2
    assert "requires" in capsys.readouterr().err