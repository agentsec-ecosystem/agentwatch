"""HTTP/SSE MCP proxy tests (M10 N1 #212)."""

from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar

import pytest

import agentwatch.hook as hook_module
from agentwatch import mcp_proxy


class _UpstreamHandler(BaseHTTPRequestHandler):
    """A tiny MCP-ish HTTP/SSE upstream used to prove the proxy forwards + records."""

    protocol_version = "HTTP/1.1"
    seen: ClassVar[list[dict[str, Any]]] = []

    def log_message(self, *args: Any) -> None:
        pass

    def _reply(self, reply: Any) -> bytes:
        payload = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        return payload

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        self.seen.append({"headers": dict(self.headers), "body": body, "path": self.path})
        message = json.loads(body) if body else {}
        reply: Any
        if isinstance(message, list):  # JSON-RPC batch
            reply = [
                {
                    "jsonrpc": "2.0",
                    "id": item.get("id"),
                    "result": {"ok": True} if item.get("method") == "tools/call" else {},
                }
                for item in message
            ]
        else:
            reply = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {"ok": True} if message.get("method") == "tools/call" else {},
            }
        if self.path.startswith("/sse"):
            frames = f"data: {json.dumps(reply)}\n\ndata: [DONE]\n\n".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(frames)))
            self.end_headers()
            self.wfile.write(frames)
            return
        self._reply(reply)

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        frames = b'data: {"jsonrpc":"2.0","id":99,"result":{"ok":true}}\n\ndata: [DONE]\n\n'
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(frames)))
        self.end_headers()
        self.wfile.write(frames)


@pytest.fixture()
def upstream() -> Iterator[ThreadingHTTPServer]:
    _UpstreamHandler.seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _UpstreamHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
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
    server = mcp_proxy.create_http_proxy(routes)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1], frames


def _request(
    port: int, method: str, path: str, body: bytes | None = None
) -> tuple[int, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Authorization": "Bearer tok", "Connection": "close"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response.status, data


def _tools_call(rpc_id: int = 7) -> bytes:
    return json.dumps(
        {"jsonrpc": "2.0", "id": rpc_id, "method": "tools/call", "params": {"name": "echo"}}
    ).encode()


def test_http_post_records_both_directions(
    monkeypatch: pytest.MonkeyPatch, upstream: ThreadingHTTPServer
) -> None:
    url = f"http://127.0.0.1:{upstream.server_address[1]}/"
    server, port, frames = _start_proxy(monkeypatch, {"echo": url})
    try:
        status, data = _request(port, "POST", "/echo", _tools_call())
        assert status == 200
        assert json.loads(data)["result"] == {"ok": True}
        assert [f["event"]["direction"] for f in frames] == ["request", "response"]
        assert frames[0]["event"]["server"] == "echo"
        assert frames[1]["event"]["tool_name"] == "echo"
    finally:
        server.shutdown()
        server.server_close()


def test_unknown_route_is_404_and_not_recorded(
    monkeypatch: pytest.MonkeyPatch, upstream: ThreadingHTTPServer
) -> None:
    url = f"http://127.0.0.1:{upstream.server_address[1]}/"
    server, port, frames = _start_proxy(monkeypatch, {"echo": url})
    try:
        status, _ = _request(port, "POST", "/nope", _tools_call())
        assert status == 404
        assert frames == []
    finally:
        server.shutdown()
        server.server_close()


def test_hop_by_hop_dropped_and_auth_preserved(
    monkeypatch: pytest.MonkeyPatch, upstream: ThreadingHTTPServer
) -> None:
    url = f"http://127.0.0.1:{upstream.server_address[1]}/"
    server, port, _ = _start_proxy(monkeypatch, {"echo": url})
    try:
        _request(port, "POST", "/echo", _tools_call())
        sent = _UpstreamHandler.seen[-1]["headers"]
        headers = {key.lower(): value for key, value in sent.items()}
        assert headers["authorization"] == "Bearer tok"
        assert headers["host"] == f"127.0.0.1:{upstream.server_address[1]}"
        assert "connection" not in headers
        assert "keep-alive" not in headers
    finally:
        server.shutdown()
        server.server_close()


def test_post_sse_response_is_recorded(
    monkeypatch: pytest.MonkeyPatch, upstream: ThreadingHTTPServer
) -> None:
    url = f"http://127.0.0.1:{upstream.server_address[1]}/sse"
    server, port, frames = _start_proxy(monkeypatch, {"echo": url})
    try:
        status, data = _request(port, "POST", "/echo", _tools_call())
        assert status == 200
        assert b"data:" in data
        assert [f["event"]["direction"] for f in frames] == ["request", "response"]
    finally:
        server.shutdown()
        server.server_close()


def test_unpaired_get_sse_response_is_not_recorded(
    monkeypatch: pytest.MonkeyPatch, upstream: ThreadingHTTPServer
) -> None:
    url = f"http://127.0.0.1:{upstream.server_address[1]}/"
    server, port, frames = _start_proxy(monkeypatch, {"echo": url})
    try:
        status, data = _request(port, "GET", "/echo")
        assert status == 200
        assert b"data:" in data
        assert frames == []
    finally:
        server.shutdown()
        server.server_close()


def test_batch_request_is_forwarded_and_tools_call_recorded(
    monkeypatch: pytest.MonkeyPatch, upstream: ThreadingHTTPServer
) -> None:
    url = f"http://127.0.0.1:{upstream.server_address[1]}/"
    server, port, frames = _start_proxy(monkeypatch, {"echo": url})
    try:
        batch = json.dumps(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "echo"},
                }
            ]
        ).encode()
        status, data = _request(port, "POST", "/echo", batch)
        assert status == 200
        assert [f["event"]["direction"] for f in frames] == ["request", "response"]
    finally:
        server.shutdown()
        server.server_close()


def test_upstream_failure_is_502_and_records_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Route to a closed port so the upstream connection fails.
    server, port, frames = _start_proxy(monkeypatch, {"echo": "http://127.0.0.1:1/"})
    try:
        status, _ = _request(port, "POST", "/echo", _tools_call())
        assert status == 502
        assert [f["event"]["direction"] for f in frames] == ["request", "response"]
        assert frames[1]["event"]["rpc"]["error"]["message"]
    finally:
        server.shutdown()
        server.server_close()


def test_create_http_proxy_requires_a_route() -> None:
    with pytest.raises(ValueError):
        mcp_proxy.create_http_proxy({})
