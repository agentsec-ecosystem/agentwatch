"""A2A interposition proxy engine (M29 A2A-1 #364, PRD 45, ADR-0025).

A2A (agent-to-agent) is the JSON-RPC 2.0 standard for cross-agent tasks. This
proxy relays an A2A client's traffic unchanged while emitting framed messages to
the agentwatch daemon over the existing Unix socket (``phase`` ``"a2a"``),
reusing the single-writer path: redaction, dedup, and the hash chain are applied
by the daemon.

It mirrors the MCP proxy (:mod:`agentwatch.mcp_proxy`): stdio relay for a local
A2A agent process, and an HTTP relay for remote agents. Only the recordable A2A
surfaces are framed (``message/send``, ``message/stream``, ``tasks/get``,
``tasks/cancel``); everything else is relay-only.
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

A2A_PHASE = "a2a"
A2A_HARNESS = "a2a-proxy"

# The A2A wire spec this proxy was built and tested against (agent↔agent
# standard v1.0). The spec is young; the proxy pins its tested range and any
# drift is a declared gap, not a silent assumption.
A2A_SPEC_VERSION = "1.0"

# The A2A surfaces this proxy frames. ``tasks/resubscribe`` and the
# push-notification-config family are documented gaps (explicitly rejected by
# the adapter, never silently dropped).
RECORDABLE_METHODS = frozenset({"message/send", "message/stream", "tasks/get", "tasks/cancel"})

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
    """Correlate proxy records to the harness session, else a fresh proxy id."""
    source = os.environ if env is None else env
    for key in ("AGENTWATCH_SESSION_ID", "CLAUDE_SESSION_ID"):
        value = source.get(key)
        if value:
            return value
    return f"a2a-{uuid.uuid4().hex[:12]}"


def _frame(
    agent: str,
    session_id: str,
    direction: str,
    *,
    rpc: Mapping[str, Any] | None = None,
    tool_name: str | None = None,
    call_id: str | None = None,
    task_id: str | None = None,
    message_id: str | None = None,
    context_id: str | None = None,
    remote_org: str | None = None,
    parent_span_id: str | None = None,
    card: Mapping[str, Any] | None = None,
    source: str | None = None,
    timestamp: str | None = None,
    cwd: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "agent": agent,
        "session_id": session_id,
        "direction": direction,
    }
    for key, value in (
        ("rpc", dict(rpc) if rpc is not None else None),
        ("tool_name", tool_name),
        ("call_id", call_id),
        ("task_id", task_id),
        ("message_id", message_id),
        ("context_id", context_id),
        ("remote_org", remote_org),
        ("parent_span_id", parent_span_id),
        ("card", dict(card) if card is not None else None),
        ("source", source),
        ("timestamp", timestamp),
        ("cwd", cwd),
        ("trace_id", trace_id),
    ):
        if value is not None:
            event[key] = value
    return {"phase": A2A_PHASE, "harness": A2A_HARNESS, "event": event}


def request_frame(
    agent: str,
    session_id: str,
    rpc: Mapping[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    """Frame a client -> agent A2A request."""
    return _frame(agent, session_id, "request", rpc=rpc, **kwargs)


def response_frame(
    agent: str,
    session_id: str,
    rpc: Mapping[str, Any],
    *,
    tool_name: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Frame an agent -> client A2A response (carries the surface name)."""
    return _frame(agent, session_id, "response", rpc=rpc, tool_name=tool_name, **kwargs)


def card_frame(
    agent: str,
    session_id: str,
    card: Mapping[str, Any],
    *,
    source: str = "server",
    **kwargs: Any,
) -> dict[str, Any]:
    """Frame an A2A agent-card exchange."""
    return _frame(agent, session_id, "card", card=card, source=source, **kwargs)


def is_jsonrpc_response(message: Any) -> bool:
    """Whether ``message`` is a JSON-RPC response (no method, has an id)."""
    return isinstance(message, Mapping) and "method" not in message and "id" in message


def is_recordable_request(message: Any) -> bool:
    """Whether ``message`` is a JSON-RPC request for a recorded A2A surface."""
    return (
        isinstance(message, Mapping)
        and message.get("method") in RECORDABLE_METHODS
    )


def _request_metadata(message: Mapping[str, Any]) -> dict[str, str]:
    """The correlation ids carried by a recordable A2A request."""
    params = message.get("params")
    if not isinstance(params, Mapping):
        return {}
    metadata: dict[str, str] = {}
    method = message.get("method")
    if method in ("message/send", "message/stream"):
        raw_message = params.get("message")
        if isinstance(raw_message, Mapping):
            for key, field in (
                ("task_id", "taskId"),
                ("message_id", "messageId"),
                ("context_id", "contextId"),
            ):
                value = raw_message.get(field)
                if isinstance(value, str) and value:
                    metadata[key] = value
    else:  # tasks/get, tasks/cancel
        value = params.get("id")
        if isinstance(value, str) and value:
            metadata["task_id"] = value
    return metadata


class Recorder:
    """Pairs A2A requests with their responses and emits frames to the daemon."""

    def __init__(
        self,
        agent: str,
        session_id: str,
        *,
        socket_path: str | None = None,
        cwd: str | None = None,
        remote_org: str | None = None,
    ) -> None:
        self.agent = agent
        self.session_id = session_id
        self.socket_path = socket_path
        self.cwd = cwd
        self.remote_org = remote_org
        self._pending: dict[Any, dict[str, Any]] = {}

    def observe_from_harness(self, message: Any) -> None:
        """Record a client -> agent request; other methods are relay-only."""
        if not is_recordable_request(message):
            return
        method = str(message.get("method"))
        metadata = _request_metadata(message)
        call_id = uuid.uuid4().hex
        record: dict[str, Any] = {
            "tool_name": method,
            "call_id": call_id,
            **metadata,
        }
        if self.remote_org is not None:
            record["remote_org"] = self.remote_org
        with contextlib.suppress(TypeError):  # an unhashable id cannot be paired
            self._pending[message.get("id")] = record
        self._emit(
            request_frame(self.agent, self.session_id, message, cwd=self.cwd, **record)
        )

    def observe_from_server(self, message: Any) -> None:
        """Record an agent -> client response for the request it answers."""
        if not isinstance(message, Mapping):
            return
        try:
            record = self._pending.pop(message.get("id"))
        except (KeyError, TypeError):
            return
        self._emit(
            response_frame(self.agent, self.session_id, message, cwd=self.cwd, **record)
        )

    def record_card(self, card: Mapping[str, Any], *, source: str = "server") -> None:
        """Record an agent-card exchange."""
        self._emit(
            card_frame(self.agent, self.session_id, card, source=source, cwd=self.cwd)
        )

    def flush_pending(self, reason: str = "server exited") -> None:
        """Record an error response for every request the server never answered."""
        for rpc_id in list(self._pending):
            record = self._pending.pop(rpc_id)
            rpc = {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": _SERVER_EXIT_CODE, "message": reason},
            }
            self._emit(
                response_frame(self.agent, self.session_id, rpc, cwd=self.cwd, **record)
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
    """Relay client -> agent, recording each request before it is sent."""
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
    """Relay agent -> client, recording each response as it arrives."""
    for line in stream:
        out.write(line)
        out.flush()
        recorder.observe_from_server(_parse(line))


def run_stdio(
    agent: str,
    command: Sequence[str],
    *,
    socket_path: str | None = None,
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | None = None,
    env: Mapping[str, str] | None = None,
    remote_org: str | None = None,
) -> int:
    """Relay a stdio A2A agent, recording task traffic.

    ``command`` is the real agent process; the proxy spawns it and passes bytes
    through unchanged. Returns the child's exit code. An in-flight request the
    agent never answers is recorded as a transport error, never dropped.
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
        raise RuntimeError("failed to open A2A agent pipes")
    recorder = Recorder(
        agent,
        resolve_session_id(env),
        socket_path=socket_path,
        cwd=os.getcwd(),
        remote_org=remote_org,
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


def _card_from_body(body: bytes) -> Mapping[str, Any] | None:
    """Parse an agent card from a response body; ``None`` when it is not one."""
    parsed = _parse(body)
    if isinstance(parsed, Mapping) and "name" in parsed:
        return parsed
    return None


class _ProxyHandler(BaseHTTPRequestHandler):
    """Relay one A2A HTTP route while recording task and card traffic."""

    protocol_version = "HTTP/1.1"
    server_version = "agentwatch-a2a-proxy"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        """Silence per-request logging (records, not stdout, are the signal)."""

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        self._proxy("GET")

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        self._proxy("POST")

    def _agent_name(self) -> str | None:
        path = urlsplit(self.path).path
        name = path.lstrip("/").split("/", 1)[0]
        server = self.server
        assert isinstance(server, _ProxyServer)
        return name if name in server.routes else None

    def _proxy(self, method: str) -> None:
        server = self.server
        assert isinstance(server, _ProxyServer)
        agent_name = self._agent_name()
        if agent_name is None:
            self.send_error(404, "unknown A2A route")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length > 0 else b""

        recorder = server.recorders[agent_name]
        request_messages = _records_from_payload(_parse(body)) if body else []
        for message in request_messages:
            recorder.observe_from_harness(message)

        upstream = server.routes[agent_name]
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
                collected += chunk
        except (OSError, http.client.HTTPException):
            pass
        finally:
            connection.close()
            self.close_connection = True

        if method == "GET":
            card = _card_from_body(bytes(collected)) if collected else None
            if card is not None:
                recorder.record_card(card, source="server")
        elif collected:
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
            if is_recordable_request(message):
                recorder.observe_from_server(
                    {
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "error": {"code": _SERVER_EXIT_CODE, "message": reason},
                    }
                )
        with contextlib.suppress(OSError, ValueError):
            self.send_error(502, "A2A upstream unreachable")


class _ProxyServer(ThreadingHTTPServer):
    """A loopback HTTP server holding the route map and one recorder per agent."""

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
) -> _ProxyServer:
    """Bind a loopback A2A proxy, one route per ``agent -> upstream URL``.

    The returned server is bound but not serving; call ``serve_forever()`` to
    run it, or ``shutdown()`` from another thread. An occupied port raises
    ``OSError`` (fail closed).
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
    """Serve the A2A proxy until interrupted; returns an exit code."""
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
    """Run the A2A proxy in stdio or HTTP mode.

    stdio: ``agentwatch-a2a-proxy --agent NAME -- CMD ...``
    HTTP:  ``agentwatch-a2a-proxy --http --route NAME=URL ...``
    """
    parser = argparse.ArgumentParser(prog="agentwatch-a2a-proxy")
    parser.add_argument("--agent", default=None, help="stdio mode: A2A agent name")
    parser.add_argument("--socket", default=None, help="daemon socket path override")
    parser.add_argument("--remote-org", default=None, help="remote organization (delegation)")
    parser.add_argument("--http", action="store_true", help="serve HTTP routes")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind host (default loopback)")
    parser.add_argument(
        "--port", type=int, default=8766, help="HTTP bind port (default 8766; 0 = ephemeral)"
    )
    parser.add_argument(
        "--route", action="append", default=[], metavar="NAME=URL", help="HTTP route (repeatable)"
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- <agent command> [args...]")
    args = parser.parse_args(argv)

    if args.http:
        try:
            routes = parse_routes(args.route)
        except ValueError as exc:
            print(f"agentwatch-a2a-proxy: {exc}", file=sys.stderr)
            return 2
        if not routes:
            print(
                "agentwatch-a2a-proxy: --http requires at least one --route NAME=URL",
                file=sys.stderr,
            )
            return 2
        return serve_http(routes, host=args.host, port=args.port, socket_path=args.socket)

    command: list[str] = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command or args.agent is None:
        print(
            "agentwatch-a2a-proxy: requires --agent NAME -- <agent command> [args...]",
            file=sys.stderr,
        )
        return 2
    return run_stdio(
        args.agent, command, socket_path=args.socket, remote_org=args.remote_org
    )


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())