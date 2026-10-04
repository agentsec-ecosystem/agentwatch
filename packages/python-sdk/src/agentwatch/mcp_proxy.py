"""MCP interposition proxy engine (M10 N1 #83).

The proxy relays a harness's MCP traffic unchanged while emitting framed
messages to the agentwatch daemon over the existing Unix socket (``phase``
``"mcp"``), reusing the single-writer path: redaction, dedup, and the hash
chain are all applied by the daemon.

This module holds the framing, request/response pairing, and session
resolution helpers. Any MCP-speaking harness can be recorded by pointing it at
``agentwatch mcp-proxy`` (stdio).
"""

from __future__ import annotations

import argparse
import contextlib
import http.client
import json
import os
import ssl
import subprocess
import sys
import threading
import uuid
from collections.abc import Mapping, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import IO, Any, BinaryIO
from urllib.parse import urlsplit

from agentwatch import hook
from agentwatch.spool import Spool

# JSON-RPC server-error code used for a request the server never answered.
_SERVER_EXIT_CODE = -32000

# Headers never forwarded verbatim: hop-by-hop (RFC 7230 §6.1) plus the framing
# headers we recompute for the proxied request/response.
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)


def resolve_session_id(env: Mapping[str, str] | None = None) -> str:
    """Correlate proxy records to the harness session, else a fresh proxy id.

    Prefers ``AGENTWATCH_SESSION_ID``, then ``CLAUDE_SESSION_ID``; otherwise a
    generated ``mcp-<12 hex>`` so a proxy run without a harness session is still
    grouped deterministically.
    """
    source = os.environ if env is None else env
    for key in ("AGENTWATCH_SESSION_ID", "CLAUDE_SESSION_ID"):
        value = source.get(key)
        if value:
            return value
    return f"mcp-{uuid.uuid4().hex[:12]}"


def _frame(
    server: str,
    session_id: str,
    direction: str,
    rpc: Mapping[str, Any],
    *,
    tool_name: str | None = None,
    call_id: str | None = None,
    timestamp: str | None = None,
    cwd: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "server": server,
        "session_id": session_id,
        "direction": direction,
        "rpc": dict(rpc),
    }
    if tool_name is not None:
        event["tool_name"] = tool_name
    if call_id is not None:
        event["call_id"] = call_id
    if timestamp is not None:
        event["timestamp"] = timestamp
    if cwd is not None:
        event["cwd"] = cwd
    return {"phase": "mcp", "harness": "mcp-proxy", "event": event}


def request_frame(
    server: str,
    session_id: str,
    rpc: Mapping[str, Any],
    *,
    call_id: str | None = None,
    timestamp: str | None = None,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Frame a harness -> server JSON-RPC request."""
    return _frame(server, session_id, "request", rpc, call_id=call_id, timestamp=timestamp, cwd=cwd)


def response_frame(
    server: str,
    session_id: str,
    rpc: Mapping[str, Any],
    *,
    tool_name: str,
    call_id: str | None = None,
    timestamp: str | None = None,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Frame a server -> harness JSON-RPC response (carries the tool name)."""
    return _frame(
        server,
        session_id,
        "response",
        rpc,
        tool_name=tool_name,
        call_id=call_id,
        timestamp=timestamp,
        cwd=cwd,
    )


def is_tools_call_request(message: Any) -> bool:
    """Whether ``message`` is a JSON-RPC ``tools/call`` request with a tool name."""
    if not isinstance(message, Mapping):
        return False
    if message.get("method") != "tools/call":
        return False
    params = message.get("params")
    if not isinstance(params, Mapping):
        return False
    name = params.get("name")
    return isinstance(name, str) and bool(name)


class Recorder:
    """Pairs MCP requests with their responses and emits frames to the daemon."""

    def __init__(
        self,
        server: str,
        session_id: str,
        *,
        socket_path: str | None = None,
        cwd: str | None = None,
    ) -> None:
        self.server = server
        self.session_id = session_id
        self.socket_path = socket_path
        self.cwd = cwd
        self._pending: dict[Any, tuple[str, str]] = {}

    def observe_from_harness(self, message: Any) -> None:
        """Record a harness -> server frame; non-``tools/call`` is relay-only."""
        if not is_tools_call_request(message):
            return
        params = message.get("params")
        name = params.get("name") if isinstance(params, Mapping) else None
        # A fresh id per call: a JSON-RPC id may be reused across calls, but the
        # daemon's dedup key must stay unique so no record is silently dropped.
        call_id = uuid.uuid4().hex
        with contextlib.suppress(TypeError):  # an unhashable JSON-RPC id cannot be paired
            self._pending[message.get("id")] = (str(name), call_id)
        self._emit(
            request_frame(self.server, self.session_id, message, call_id=call_id, cwd=self.cwd)
        )

    def observe_from_server(self, message: Any) -> None:
        """Record a server -> harness frame when it answers a seen request."""
        if not isinstance(message, Mapping):
            return
        try:
            tool_name, call_id = self._pending.pop(message.get("id"))
        except (KeyError, TypeError):
            return
        self._emit(
            response_frame(
                self.server,
                self.session_id,
                message,
                tool_name=tool_name,
                call_id=call_id,
                cwd=self.cwd,
            )
        )

    def flush_pending(self, reason: str = "server exited") -> None:
        """Record an error response for every request the server never answered."""
        for rpc_id in list(self._pending):
            tool_name, call_id = self._pending.pop(rpc_id)
            rpc = {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": _SERVER_EXIT_CODE, "message": reason},
            }
            self._emit(
                response_frame(
                    self.server,
                    self.session_id,
                    rpc,
                    tool_name=tool_name,
                    call_id=call_id,
                    cwd=self.cwd,
                )
            )

    def _emit(self, frame: dict[str, Any]) -> None:
        """Send a frame; spool it when the daemon is unreachable (never raise)."""
        if hook.send(frame, socket_path=self.socket_path):
            return
        spool_path = (self.socket_path or hook.default_spool_path()) + ".spool"
        with contextlib.suppress(OSError, ValueError):
            Spool(spool_path).append(frame)


def _parse(line: bytes) -> Any:
    """Parse one relayed line; malformed input is contained, never fatal."""
    try:
        return json.loads(line)
    except ValueError:
        return None


def _pump_harness(stream: BinaryIO, child_stdin: IO[bytes], recorder: Recorder) -> None:
    """Relay harness -> server, recording each request before it is sent."""
    try:
        for line in stream:
            recorder.observe_from_harness(_parse(line))
            try:
                child_stdin.write(line)
                child_stdin.flush()
            except OSError:
                break
    finally:
        with contextlib.suppress(OSError, ValueError):
            child_stdin.close()


def _pump_server(stream: IO[bytes], out: BinaryIO, recorder: Recorder) -> None:
    """Relay server -> harness, recording each response as it arrives."""
    for line in stream:
        out.write(line)
        out.flush()
        recorder.observe_from_server(_parse(line))


def run_stdio(
    server_name: str,
    command: Sequence[str],
    *,
    socket_path: str | None = None,
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | None = None,
    env: Mapping[str, str] | None = None,
) -> int:
    """Relay a stdio MCP server, recording ``tools/call`` traffic.

    ``command`` is the real server; the proxy spawns it and passes bytes through
    unchanged. Returns the child's exit code. An in-flight request the server
    never answers is recorded as an error (transport failure), never dropped.
    """
    in_stream = stdin if stdin is not None else sys.stdin.buffer
    out_stream = stdout if stdout is not None else sys.stdout.buffer
    child = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        env={**os.environ, **(env or {})},
    )
    child_in, child_out = child.stdin, child.stdout
    if child_in is None or child_out is None:  # pragma: no cover - pipes always open
        raise RuntimeError("failed to open MCP server pipes")
    recorder = Recorder(
        server_name, resolve_session_id(env), socket_path=socket_path, cwd=os.getcwd()
    )
    pump = threading.Thread(target=_pump_harness, args=(in_stream, child_in, recorder), daemon=True)
    pump.start()
    _pump_server(child_out, out_stream, recorder)
    pump.join()
    child.wait()
    recorder.flush_pending("server exited")
    return child.returncode if child.returncode is not None else 0


def _records_from_payload(payload: Any) -> list[Mapping[str, Any]]:
    """Return the JSON-RPC messages in a single object or a top-level batch array."""
    if isinstance(payload, Mapping):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    return []


def _sse_data(chunk: bytes) -> bytes | None:
    """Extract the payload of one SSE ``data:`` line, or None for other lines."""
    line = chunk.rstrip(b"\r").strip()
    if not line.startswith(b"data:"):
        return None
    data = line[len(b"data:") :].strip()
    if not data or data == b"[DONE]":
        return None
    return data


class _SseParser:
    """Incrementally turn an SSE byte stream into JSON-RPC messages."""

    def __init__(self) -> None:
        self._buffer = b""

    def feed(self, chunk: bytes) -> list[Mapping[str, Any]]:
        self._buffer += chunk
        messages: list[Mapping[str, Any]] = []
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            data = _sse_data(line)
            if data is not None:
                messages.extend(_records_from_payload(_parse(data)))
        return messages


class _ProxyHandler(BaseHTTPRequestHandler):
    """Relay one MCP HTTP/SSE route while recording ``tools/call`` traffic."""

    protocol_version = "HTTP/1.1"
    server_version = "agentwatch-mcp-proxy"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        """Silence per-request logging (records, not stdout, are the signal)."""

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        self._proxy("GET")

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        self._proxy("POST")

    def _server_name(self) -> str | None:
        path = urlsplit(self.path).path
        name = path.lstrip("/").split("/", 1)[0]
        server = self.server
        assert isinstance(server, _ProxyServer)
        return name if name in server.routes else None

    def _proxy(self, method: str) -> None:
        server = self.server
        assert isinstance(server, _ProxyServer)
        server_name = self._server_name()
        if server_name is None:
            self.send_error(404, "unknown MCP route")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length > 0 else b""

        recorder = server.recorders[server_name]
        request_messages = _records_from_payload(_parse(body)) if body else []
        for message in request_messages:
            recorder.observe_from_harness(message)

        upstream = server.routes[server_name]
        parts = urlsplit(upstream)
        target = parts.path or "/"
        if parts.query:
            target = f"{target}?{parts.query}"

        hostname = parts.hostname or ""
        connection: http.client.HTTPConnection
        if parts.scheme == "https":
            connection = http.client.HTTPSConnection(
                hostname, parts.port or 443, timeout=30, context=ssl.create_default_context()
            )
        else:
            connection = http.client.HTTPConnection(hostname, parts.port or 80, timeout=30)

        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in _HOP_BY_HOP and key.lower() not in ("host", "content-length")
        }
        headers["Host"] = parts.netloc
        try:
            connection.request(
                method, target, body=body if method != "GET" else None, headers=headers
            )
            response = connection.getresponse()
        except (OSError, http.client.HTTPException) as exc:
            connection.close()
            self._upstream_error(recorder, request_messages, str(exc))
            return

        content_type = response.getheader("Content-Type", "") or ""
        is_sse = "text/event-stream" in content_type.lower()
        parser = _SseParser()
        collected = bytearray()

        self.send_response(response.status)
        for key, value in response.getheaders():
            if key.lower() in _HOP_BY_HOP or key.lower() == "content-length":
                continue
            self.send_header(key, value)
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            while True:
                chunk = response.read(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
                if is_sse:
                    for message in parser.feed(chunk):
                        recorder.observe_from_server(message)
                else:
                    collected += chunk
        except (OSError, http.client.HTTPException):
            pass
        finally:
            connection.close()
            self.close_connection = True

        if not is_sse and collected:
            for message in _records_from_payload(_parse(bytes(collected))):
                recorder.observe_from_server(message)

    def _upstream_error(
        self,
        recorder: Recorder,
        request_messages: list[Mapping[str, Any]],
        reason: str,
    ) -> None:
        """Relay a transport failure as a 502 and record it as an error outcome."""
        for message in request_messages:
            if is_tools_call_request(message):
                recorder.observe_from_server(
                    {
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "error": {"code": _SERVER_EXIT_CODE, "message": reason},
                    }
                )
        with contextlib.suppress(OSError, ValueError):
            self.send_error(502, "MCP upstream unreachable")


class _ProxyServer(ThreadingHTTPServer):
    """A loopback HTTP server holding the route map and one recorder per server."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        routes: Mapping[str, str],
        recorders: Mapping[str, Recorder],
    ) -> None:
        super().__init__(address, _ProxyHandler)
        self.routes = dict(routes)
        self.recorders = dict(recorders)


def create_http_proxy(
    routes: Mapping[str, str],
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    socket_path: str | None = None,
) -> ThreadingHTTPServer:
    """Bind a loopback MCP HTTP/SSE proxy, one route per ``server -> upstream URL``.

    The returned server is bound but not serving; call ``serve_forever()`` to run
    it, or ``shutdown()`` from another thread. An occupied port raises ``OSError``
    (fail closed, D-M6).
    """
    if not routes:
        raise ValueError("create_http_proxy requires at least one route")
    session_id = resolve_session_id()
    cwd = os.getcwd()
    recorders = {
        name: Recorder(name, session_id, socket_path=socket_path, cwd=cwd) for name in routes
    }
    return _ProxyServer((host, port), routes, recorders)


def serve_http(
    routes: Mapping[str, str],
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    socket_path: str | None = None,
) -> int:
    """Serve the HTTP/SSE MCP proxy until interrupted; returns an exit code."""
    server = create_http_proxy(routes, host=host, port=port, socket_path=socket_path)
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - interactive shutdown
        pass
    finally:
        server.server_close()
    return 0


def parse_routes(routes: Sequence[str]) -> dict[str, str]:
    """Parse ``--route NAME=URL`` pairs; raise ``ValueError`` on malformed input."""
    parsed: dict[str, str] = {}
    for item in routes:
        name, sep, url = item.partition("=")
        name = name.strip()
        url = url.strip()
        if not sep or not name or not url:
            raise ValueError(f"invalid route {item!r}; expected NAME=URL")
        if urlsplit(url).scheme not in ("http", "https"):
            raise ValueError(f"invalid route {item!r}; URL must be http(s)")
        parsed[name] = url
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    """Run the MCP proxy in stdio or HTTP mode.

    stdio: ``agentwatch-mcp-proxy --server NAME -- CMD ...``
    HTTP:  ``agentwatch-mcp-proxy --http --route NAME=URL ...``
    """
    parser = argparse.ArgumentParser(prog="agentwatch-mcp-proxy")
    parser.add_argument("--server", default=None, help="stdio mode: MCP server name")
    parser.add_argument("--socket", default=None, help="daemon socket path override")
    parser.add_argument("--http", action="store_true", help="serve HTTP/SSE routes")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind host (default loopback)")
    parser.add_argument(
        "--port", type=int, default=8765, help="HTTP bind port (default 8765; 0 = ephemeral)"
    )
    parser.add_argument(
        "--route", action="append", default=[], metavar="NAME=URL", help="HTTP route (repeatable)"
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- <server command> [args...]")
    args = parser.parse_args(argv)

    if args.http:
        try:
            routes = parse_routes(args.route)
        except ValueError as exc:
            print(f"agentwatch-mcp-proxy: {exc}", file=sys.stderr)
            return 2
        if not routes:
            print(
                "agentwatch-mcp-proxy: --http requires at least one --route NAME=URL",
                file=sys.stderr,
            )
            return 2
        return serve_http(routes, host=args.host, port=args.port, socket_path=args.socket)

    command: list[str] = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command or args.server is None:
        print(
            "agentwatch-mcp-proxy: requires --server NAME -- <server command> [args...]",
            file=sys.stderr,
        )
        return 2
    return run_stdio(args.server, command, socket_path=args.socket)


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
