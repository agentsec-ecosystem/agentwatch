"""HTTP A2A proxy tests (M29 A2A-1 #364)."""

from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar

import pytest

import agentwatch.hook as hook_module
from agentwatch import a2a_proxy

CARD = {
    "name": "Remote Scheduler",
    "url": "https://scheduler.acme.example/a2a",
    "version": "1.0.0",
    "provider": {"organization": "Acme"},
}


class _UpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen: ClassVar[list[dict[str, Any]]] = []

    def log_message(self, *args: Any) -> None:
        pass

    def _reply(self, payload: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        self.seen.append({"headers": dict(self.headers), "body": body, "path": self.path})
        message = json.loads(body) if body else {}
        reply = {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {"kind": "task", "id": "t-1", "status": {"state": "completed"}},
        }
        self._reply(json.dumps(reply).encode(), "application/json")

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        self._reply(json.dumps(CARD).encode(), "application/json")


@pytest.fixture()
def upstream() -> Iterator[ThreadingHTTPServer]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _UpstreamHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _start_proxy(
    monkeypatch: pytest.MonkeyPatch, routes: dict[str, str]
) -> tuple[ThreadingHTTPServer, int, list[dict[str, Any]]]:
    frames: list[dict[str, Any]] = []

    def fake_send(message: dict[str, Any], **_: Any) -> bool:
        frames.append(message)
        return True

    monkeypatch.setattr(hook_module, "send", fake_send)
    server = a2a_proxy.create_http_proxy(routes)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1], frames


def _request(port: int, method: str, path: str, body: bytes | None = None) -> tuple[int, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Connection": "close"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response.status, data


def _send(rpc_id: int = 7) -> bytes:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": "message/send",
            "params": {"message": {"messageId": "m-1", "taskId": "t-1"}},
        }
    ).encode()


def test_http_post_records_both_directions(
    monkeypatch: pytest.MonkeyPatch, upstream: ThreadingHTTPServer
) -> None:
    url = f"http://127.0.0.1:{upstream.server_address[1]}/"
    server, port, frames = _start_proxy(monkeypatch, {"scheduler": url})
    try:
        status, data = _request(port, "POST", "/scheduler", _send())
        assert status == 200
        assert json.loads(data)["result"]["kind"] == "task"
        assert [f["event"]["direction"] for f in frames] == ["request", "response"]
        assert frames[0]["event"]["agent"] == "scheduler"
        assert frames[1]["event"]["tool_name"] == "message/send"
    finally:
        server.shutdown()
        server.server_close()


def test_http_card_fetch_is_recorded(
    monkeypatch: pytest.MonkeyPatch, upstream: ThreadingHTTPServer
) -> None:
    url = f"http://127.0.0.1:{upstream.server_address[1]}/"
    server, port, frames = _start_proxy(monkeypatch, {"scheduler": url})
    try:
        status, data = _request(port, "GET", "/scheduler/.well-known/agent-card.json")
        assert status == 200
        assert json.loads(data)["name"] == "Remote Scheduler"
        assert [f["event"]["direction"] for f in frames] == ["card"]
        assert frames[0]["event"]["card"]["provider"]["organization"] == "Acme"
    finally:
        server.shutdown()
        server.server_close()


def test_unknown_route_is_404_and_not_recorded(
    monkeypatch: pytest.MonkeyPatch, upstream: ThreadingHTTPServer
) -> None:
    url = f"http://127.0.0.1:{upstream.server_address[1]}/"
    server, port, frames = _start_proxy(monkeypatch, {"scheduler": url})
    try:
        status, _ = _request(port, "POST", "/nope", _send())
        assert status == 404
        assert frames == []
    finally:
        server.shutdown()
        server.server_close()


def test_upstream_failure_is_502_and_records_error(monkeypatch: pytest.MonkeyPatch) -> None:
    server, port, frames = _start_proxy(monkeypatch, {"scheduler": "http://127.0.0.1:1/"})
    try:
        status, _ = _request(port, "POST", "/scheduler", _send())
        assert status == 502
        assert [f["event"]["direction"] for f in frames] == ["request", "response"]
        assert frames[1]["event"]["rpc"]["error"]["message"]
    finally:
        server.shutdown()
        server.server_close()


def test_create_http_proxy_requires_a_route() -> None:
    with pytest.raises(ValueError):
        a2a_proxy.create_http_proxy({})