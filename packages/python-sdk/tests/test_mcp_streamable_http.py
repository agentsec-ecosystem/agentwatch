"""Streamable HTTP transport tests (M27 MCP-1 #333).

The MCP spec revised to 2026-07-28 (ADR-0023): Streamable HTTP is the primary
transport and **sessions are removed**. The proxy therefore serves the
streamable transport statelessly — it neither requires, forwards, nor emits
``Mcp-Session-Id`` — while keeping the legacy HTTP/SSE relay verbatim
(deprecated-in-spec). ``MCP-Protocol-Version`` is relayed unchanged.
"""

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
from agentwatch.cli.main import main


class _UpstreamHandler(BaseHTTPRequestHandler):
    """A tiny MCP-ish upstream that echoes a session id and records headers."""

    protocol_version = "HTTP/1.1"
    seen: ClassVar[list[dict[str, Any]]] = []
    session_id: ClassVar[str] = ""

    def log_message(self, *args: Any) -> None:
        pass

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        self.seen.append({"headers": dict(self.headers), "body": body})
        message = json.loads(body) if body else {}
        reply = {"jsonrpc": "2.0", "id": message.get("id"), "result": {"ok": True}}
        payload = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        if _UpstreamHandler.session_id:
            self.send_header("Mcp-Session-Id", _UpstreamHandler.session_id)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture()
def upstream() -> Iterator[ThreadingHTTPServer]:
    _UpstreamHandler.seen = []
    _UpstreamHandler.session_id = ""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _UpstreamHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _start_proxy(
    monkeypatch: pytest.MonkeyPatch,
    routes: dict[str, str],
    *,
    transport: str | None = None,
) -> tuple[ThreadingHTTPServer, int, list[dict[str, Any]]]:
    frames: list[dict[str, Any]] = []

    def fake_send(message: dict[str, Any], **_: Any) -> bool:
        frames.append(message)
        return True

    monkeypatch.setattr(hook_module, "send", fake_send)
    server = (
        mcp_proxy.create_http_proxy(routes)
        if transport is None
        else mcp_proxy.create_http_proxy(routes, transport=transport)
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1], frames


def _request(
    port: int,
    method: str,
    path: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    request_headers = {"Connection": "close"}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request_headers.update(headers or {})
    connection.request(method, path, body=body, headers=request_headers)
    response = connection.getresponse()
    data = response.read()
    result = response.status, data, dict(response.getheaders())
    connection.close()
    return result


def _tools_call() -> bytes:
    return json.dumps(
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "echo"}}
    ).encode()


def _lower(headers: dict[str, str]) -> dict[str, str]:
    return {key.lower(): value for key, value in headers.items()}


def test_transports_are_declared_with_a_streamable_default() -> None:
    assert mcp_proxy.MCP_TRANSPORT_STREAMABLE == "streamable-http"
    assert mcp_proxy.MCP_TRANSPORT_HTTP_SSE == "http-sse"
    assert frozenset({"streamable-http", "http-sse"}) == mcp_proxy.MCP_TRANSPORTS

    server = mcp_proxy.create_http_proxy({"echo": "http://127.0.0.1:1/"})
    try:
        assert server.transport == mcp_proxy.MCP_TRANSPORT_STREAMABLE
    finally:
        server.server_close()


def test_streamable_transport_strips_session_id_both_directions(
    monkeypatch: pytest.MonkeyPatch, upstream: ThreadingHTTPServer
) -> None:
    _UpstreamHandler.session_id = "srv-session"
    url = f"http://127.0.0.1:{upstream.server_address[1]}/"
    server, port, _ = _start_proxy(monkeypatch, {"echo": url})
    try:
        status, _, response_headers = _request(
            port,
            "POST",
            "/echo",
            _tools_call(),
            headers={"Mcp-Session-Id": "client-session"},
        )
        assert status == 200
        sent = _lower(_UpstreamHandler.seen[-1]["headers"])
        assert "mcp-session-id" not in sent  # sessions removed: never forwarded upstream
        assert "mcp-session-id" not in _lower(response_headers)  # never leaked back
    finally:
        server.shutdown()
        server.server_close()


def test_legacy_http_sse_transport_keeps_session_id(
    monkeypatch: pytest.MonkeyPatch, upstream: ThreadingHTTPServer
) -> None:
    _UpstreamHandler.session_id = "srv-session"
    url = f"http://127.0.0.1:{upstream.server_address[1]}/"
    server, port, _ = _start_proxy(monkeypatch, {"echo": url}, transport="http-sse")
    try:
        status, _, response_headers = _request(
            port,
            "POST",
            "/echo",
            _tools_call(),
            headers={"Mcp-Session-Id": "client-session"},
        )
        assert status == 200
        assert _lower(_UpstreamHandler.seen[-1]["headers"])["mcp-session-id"] == "client-session"
        assert _lower(response_headers)["mcp-session-id"] == "srv-session"
    finally:
        server.shutdown()
        server.server_close()


def test_streamable_transport_relays_protocol_version(
    monkeypatch: pytest.MonkeyPatch, upstream: ThreadingHTTPServer
) -> None:
    url = f"http://127.0.0.1:{upstream.server_address[1]}/"
    server, port, frames = _start_proxy(monkeypatch, {"echo": url})
    try:
        status, _, _ = _request(
            port,
            "POST",
            "/echo",
            _tools_call(),
            headers={
                "MCP-Protocol-Version": "2026-07-28",
                "Accept": "application/json, text/event-stream",
            },
        )
        assert status == 200
        sent = _lower(_UpstreamHandler.seen[-1]["headers"])
        assert sent["mcp-protocol-version"] == "2026-07-28"
        assert sent["accept"] == "application/json, text/event-stream"
        assert [f["event"]["direction"] for f in frames] == ["request", "response"]
    finally:
        server.shutdown()
        server.server_close()


def test_streamable_transport_requires_no_session(
    monkeypatch: pytest.MonkeyPatch, upstream: ThreadingHTTPServer
) -> None:
    url = f"http://127.0.0.1:{upstream.server_address[1]}/"
    server, port, _ = _start_proxy(monkeypatch, {"echo": url})
    try:
        status, data, _ = _request(port, "POST", "/echo", _tools_call())
        assert status == 200
        assert json.loads(data)["result"] == {"ok": True}
    finally:
        server.shutdown()
        server.server_close()


def test_create_http_proxy_rejects_unknown_transport(upstream: ThreadingHTTPServer) -> None:
    url = f"http://127.0.0.1:{upstream.server_address[1]}/"
    with pytest.raises(ValueError):
        mcp_proxy.create_http_proxy({"echo": url}, transport="carrier-pigeon")


def test_cli_rejects_unknown_transport() -> None:
    assert (
        main(
            [
                "mcp-proxy",
                "--http",
                "--transport",
                "carrier-pigeon",
                "--route",
                "echo=http://127.0.0.1:1/",
            ]
        )
        == 2
    )
