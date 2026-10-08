"""``agentwatch ui``: a read-only, loopback browser console over the chain store.

M30 LUI-1 (PRD 54 §LUI-1, ADR-0036). One command opens a **zero-Docker** browser
view of the hook-recorded chain store: sessions → timeline/replay → record
detail, with impact/cost/coverage/oversight tabs and a read-only session export.
Live updates reuse the M25 STR transport (M30 UI-1).

Security model (ADR-0036, enumerated by tests):

* binds **loopback only** — a non-loopback ``host`` is coerced to ``127.0.0.1``;
* a **per-launch token** (``secrets.token_urlsafe``) is required on every route,
  passed in the URL or an ``X-Agentwatch-Token`` header;
* a **Host-header check** blocks DNS-rebinding (only loopback hosts accepted);
* **read-only** — no mutation endpoint exists; non-GET methods return 405;
* **no egress** — the process only serves loopback requests and reads the store.

Numbers equal the CLI ``--json`` (parity test), and chain gaps/tombstones are
rendered rather than hidden.
"""

from __future__ import annotations

import hmac
import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from agentwatch.cost import build_cost
from agentwatch.coverage import (
    build_coverage,
    default_transcript_base,
    discover_transcripts,
)
from agentwatch.impact import build_impact
from agentwatch.install import hooks_installed, resolve_scope
from agentwatch.quarantine import QuarantineLog
from agentwatch.query_index import QueryIndex, index_path_for_store
from agentwatch.replay import replay_session
from agentwatch.session_export import export_session
from agentwatch.session_state import session_states
from agentwatch.store import RecordStore
from agentwatch.view import list_sessions

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 0

_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>agentwatch console</title>
</head>
<body>
<h1>agentwatch console</h1>
<p class="read-only">read-only &middot; loopback only &middot; hash-chained store</p>
<div id="health" role="status"></div>
<div id="sessions"></div>
<script>
const params = new URLSearchParams(location.search);
const token = params.get("token") || "";
async function api(path) {
  const res = await fetch(path, {headers: {"X-Agentwatch-Token": token}});
  if (!res.ok) throw new Error(path + ": " + res.status);
  return res.json();
}
api("/api/health").then(h => {
  const el = document.getElementById("health");
  el.textContent = h.chain_ok ? "chain ok" : ("chain gap at seq " + h.broken_at);
  el.className = h.chain_ok ? "ok" : "gap";
}).catch(e => { document.getElementById("health").textContent = String(e); });
api("/api/sessions").then(s => {
  document.getElementById("sessions").innerHTML =
    s.sessions.map(x => "<div>" + x.session_id + " \\u2014 " + x.state +
      " (" + x.records + " records)</div>").join("");
});
</script>
</body>
</html>
"""


class _ConsoleHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer carrying the store, index, and launch token."""

    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        store: RecordStore,
        token: str,
        index: QueryIndex | None,
    ) -> None:
        self.store = store
        self.token = token
        self.index = index
        super().__init__(address, _ConsoleHandler)


class _ConsoleHandler(BaseHTTPRequestHandler):
    """Serve the read-only console routes; never mutate the store."""

    server_version = "agentwatch-console/0.1.0"

    # -- helpers -----------------------------------------------------------

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
        """Silence the default per-request stderr logging."""

    @property
    def _console(self) -> _ConsoleHTTPServer:
        return self.server  # type: ignore[return-value]

    def _host_ok(self) -> bool:
        host = self.headers.get("Host", "")
        if not host:
            return False
        # Strip the port; IPv6 literals are bracketed, e.g. ``[::1]:8080``.
        if host.startswith("["):
            name = host[1 : host.find("]")] if "]" in host else host[1:]
        else:
            name = host.rsplit(":", 1)[0]
        return name in LOOPBACK_HOSTS

    def _token_ok(self) -> bool:
        provided = self.headers.get("X-Agentwatch-Token")
        if provided is None:
            query = parse_qs(urlparse(self.path).query)
            tokens = query.get("token")
            provided = tokens[0] if tokens else None
        if not provided:
            return False
        return hmac.compare_digest(provided, self._console.token)

    def _authorized(self) -> bool:
        if not self._host_ok() or not self._token_ok():
            self._send_json({"error": "forbidden"}, status=403)
            return False
        return True

    def _send_json(self, payload: Any, *, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, *, content_type: str, status: int = 200) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    # -- routes ------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - stdlib signature
        if not self._authorized():
            return
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            if path == "/":
                self._send_text(_INDEX_HTML, content_type="text/html; charset=utf-8")
            elif path == "/api/health":
                self._send_json(self._health())
            elif path == "/api/sessions":
                self._send_json(self._sessions())
            elif path == "/api/cost":
                self._send_json(build_cost(self._console.store, by="session").to_dict())
            elif path == "/api/coverage":
                self._send_json(self._coverage())
            elif path == "/api/oversight":
                self._send_json(self._oversight())
            elif path.startswith("/api/session/"):
                self._send_json(self._session(unquote(path.removeprefix("/api/session/"))))
            elif path.startswith("/api/impact/"):
                self._send_json(self._impact(unquote(path.removeprefix("/api/impact/"))))
            elif path.startswith("/api/export/"):
                self._export(unquote(path.removeprefix("/api/export/")))
            elif path == "/api/live":
                self._send_json({"poll_interval_ms": 1000, "transport": "M25 STR"})
            else:
                self._send_json({"error": "not found"}, status=404)
        except KeyError as exc:
            self._send_json({"error": f"unknown session {exc}"}, status=404)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)

    def _reject_mutation(self) -> None:
        self._send_json({"error": "read-only console; no mutation endpoints"}, status=405)

    do_POST = _reject_mutation  # noqa: N815 - stdlib handler dispatch name
    do_PUT = _reject_mutation  # noqa: N815
    do_PATCH = _reject_mutation  # noqa: N815
    do_DELETE = _reject_mutation  # noqa: N815

    # -- payloads ----------------------------------------------------------

    def _health(self) -> dict[str, Any]:
        store = self._console.store
        status = store.verify()
        index = self._console.index
        payload: dict[str, Any] = {
            "chain_ok": status.ok,
            "broken_at": status.broken_at,
            "records": len(store.records()),
            "tombstones": sum(1 for entry in store.entries() if entry.tombstone),
            "parse_errors": len(store.parse_errors),
        }
        if index is not None:
            payload["index_present"] = index.exists
            payload["index_fresh"] = index.is_fresh(store) if index.exists else False
        return payload

    def _sessions(self) -> dict[str, Any]:
        store = self._console.store
        order = list_sessions(store)
        states = session_states(store, order)
        counts: dict[str, int] = {session: 0 for session in order}
        for record in store.records():
            if record.session_id in counts:
                counts[record.session_id] += 1
        return {
            "sessions": [
                {
                    "session_id": session,
                    "state": states[session].state if session in states else "unknown",
                    "records": counts[session],
                }
                for session in order
            ]
        }

    def _session(self, session_id: str) -> dict[str, Any]:
        store = self._console.store
        records = replay_session(store, session_id)
        if not records:
            raise KeyError(session_id)
        seq_by_id = {
            id(entry.record): entry.seq for entry in store.entries() if entry.record is not None
        }
        return {
            "session_id": session_id,
            "records": [
                {"seq": seq_by_id.get(id(record), 0), "record": record.to_dict()}
                for record in records
            ],
        }

    def _impact(self, session_id: str) -> dict[str, Any]:
        store = self._console.store
        report = build_impact(store, session_id)
        if report.records == 0:
            raise KeyError(session_id)
        return report.to_dict()

    def _coverage(self) -> dict[str, Any]:
        store = self._console.store
        store_dir = store.path.parent
        transcripts, present = discover_transcripts(default_transcript_base(), since=None)
        hooks_any = any(
            hooks_installed(resolve_scope(scope).settings_path) for scope in ("project", "user")
        )
        report = build_coverage(
            store,
            transcripts=transcripts,
            transcripts_present=present,
            hooks_installed=hooks_any,
            quarantine=QuarantineLog(store_dir / "quarantine.jsonl"),
        )
        return report.to_dict()

    def _oversight(self) -> dict[str, Any]:
        from agentwatch.oversight import build_oversight

        return build_oversight(self._console.store, by="source").to_dict()

    def _export(self, session_id: str) -> None:
        export = export_session(self._console.store, session_id)
        if export.count == 0:
            self._send_json({"error": f"no records for session {session_id}"}, status=404)
            return
        body = "\n".join(json.dumps(row, ensure_ascii=False) for row in export.rows)
        self._send_text(body, content_type="application/x-ndjson; charset=utf-8")


class ConsoleServer:
    """Loopback-only read-only console server, started/stopped explicitly."""

    def __init__(
        self,
        store: RecordStore,
        *,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        token: str | None = None,
        index: QueryIndex | None = None,
    ) -> None:
        self.store = store
        self.token = token or secrets.token_urlsafe(32)
        self.index = index if index is not None else QueryIndex(index_path_for_store(store.path))
        bind_host = host if host in LOOPBACK_HOSTS else DEFAULT_HOST
        self._server = _ConsoleHTTPServer((bind_host, port), store, self.token, self.index)
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    @property
    def url(self) -> str:
        host = self.address[0]
        if host in {"::1", "::", "0.0.0.0"}:
            host = DEFAULT_HOST
        return f"http://{host}:{self.address[1]}"

    def start(self) -> None:
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def serve_forever(self) -> None:
        self._server.serve_forever()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def __enter__(self) -> ConsoleServer:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()


def open_console_url(url: str) -> bool:
    """Best-effort open of the console in the default browser (never fatal)."""
    try:
        return webbrowser.open(url)
    except Exception:  # noqa: BLE001 - opening a browser must never break the console
        return False


__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "LOOPBACK_HOSTS",
    "ConsoleServer",
    "open_console_url",
]
