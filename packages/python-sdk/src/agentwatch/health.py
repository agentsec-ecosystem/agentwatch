"""Recorder self-observability: health snapshot + loopback ``/healthz`` (M5 B1).

PRD 13/NFR-12 specifies the complete health contract so an operator can tell a
clean run from "couldn't read the run". The daemon holds a thread-safe
:class:`HealthSnapshot` (chain status, store stats, self-test result, hook
activity) and serves it as JSON over a **loopback-only** stdlib
``ThreadingHTTPServer``. Health is best-effort: a busy port logs and recording
continues, because recording must never depend on the endpoint (PRD 22 B1).

The payload contains no record content -- counts, timestamps, paths, booleans
only. ``/healthz`` is not to be exposed off-host.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

from agentwatch.records import AgentRecord
from agentwatch.store import ChainStatus, RecordStore

HEALTH_PATH = "/healthz"
_BYTES_PER_MB = 1024 * 1024
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
_STOPPED_REASON = "daemon-not-running"


def _iso(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    return moment.astimezone(timezone.utc).isoformat()


def _default_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover - stdlib always present on 3.10+
        return "0.1.0"
    try:
        return version("agentwatch")
    except PackageNotFoundError:  # pragma: no cover - source checkout
        return "0.1.0"


@dataclass
class HookHealth:
    """Per-harness hook state (installed, last fire, error count)."""

    installed: bool = False
    last_fire_at: datetime | None = None
    errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "installed": self.installed,
            "last_fire_at": _iso(self.last_fire_at),
            "errors": self.errors,
        }


class HealthSnapshot:
    """Thread-safe view of the daemon's health, copied under a lock.

    Every mutator acquires ``_lock``; :meth:`to_dict` reads a consistent copy.
    State is *derived*, never assigned, so it cannot claim ``recording`` when a
    condition says otherwise (NFR-8).
    """

    def __init__(
        self,
        *,
        store_path: Path | str,
        version: str | None = None,
        pid: int | None = None,
        started_at: datetime | None = None,
        export_enabled: bool = False,
        export_endpoint: str | None = None,
        redaction_mode: str = "metadata-only",
        self_test_passing: bool = True,
        hooks_installed: bool = False,
        harness: str = "claude-code",
        durability: str = "record",
    ) -> None:
        self._lock = threading.Lock()
        self.durability = durability
        self.pid = pid if pid is not None else os.getpid()
        self.started_at = started_at or datetime.now(timezone.utc)
        self.version = version or _default_version()
        self.store_path = str(store_path)
        self.export_enabled = export_enabled
        self.export_endpoint = export_endpoint
        self.redaction_mode = redaction_mode
        self.self_test_passing = self_test_passing
        self.chain_ok = True
        self.chain_reason: str | None = None
        self.records = 0
        self.size_bytes = 0
        self.last_append_at: datetime | None = None
        self.export_last_success_at: datetime | None = None
        self.export_last_error: str | None = None
        self.stopped_reason: str | None = None
        self.clock_skew_s: float | None = None
        self.gaps: list[dict[str, Any]] = []
        self.drift: list[dict[str, Any]] = []
        self.hooks: dict[str, HookHealth] = {harness: HookHealth(installed=hooks_installed)}

    # -- mutators ----------------------------------------------------------

    def set_chain(self, status: ChainStatus) -> None:
        with self._lock:
            self.chain_ok = status.ok
            if status.ok:
                self.chain_reason = None
            else:
                location = status.broken_at
                self.chain_reason = (
                    f"chain-broken at seq {location}" if location is not None else "chain-broken"
                )

    def set_store_stats(self, *, records: int, size_bytes: int) -> None:
        with self._lock:
            self.records = records
            self.size_bytes = size_bytes

    def record_appended(self, record: AgentRecord, *, size_bytes: int) -> None:
        with self._lock:
            self.records += 1
            self.size_bytes = size_bytes
            self.last_append_at = datetime.now(timezone.utc)

    def set_self_test(self, *, passing: bool) -> None:
        with self._lock:
            self.self_test_passing = passing

    def set_export_success(self) -> None:
        with self._lock:
            self.export_last_success_at = datetime.now(timezone.utc)
            self.export_last_error = None

    def set_export_error(self, error: str) -> None:
        with self._lock:
            self.export_last_error = error

    def set_stopped(self, reason: str) -> None:
        with self._lock:
            self.stopped_reason = reason

    def clear_stopped(self) -> None:
        with self._lock:
            self.stopped_reason = None

    def note_hook_fire(self, harness: str) -> None:
        with self._lock:
            hook = self.hooks.setdefault(harness, HookHealth(installed=True))
            hook.last_fire_at = datetime.now(timezone.utc)

    def note_hook_error(self, harness: str) -> None:
        with self._lock:
            hook = self.hooks.setdefault(harness, HookHealth(installed=True))
            hook.errors += 1

    def note_gap(self, gap: dict[str, Any]) -> None:
        with self._lock:
            self.gaps.append(dict(gap))
            self.gaps = self.gaps[-8:]

    def note_clock_skew(self, seconds: float) -> None:
        """Flag a future-dated event (F9), degrading health rather than hiding it."""
        with self._lock:
            self.clock_skew_s = max(self.clock_skew_s or 0.0, seconds)
            self.gaps.append({"reason": "clock-skew", "skew_s": seconds})
            self.gaps = self.gaps[-8:]

    def note_drift(self, observation: dict[str, Any]) -> None:
        """Surface a harness-drift observation (S19); advisory, never degrading."""
        with self._lock:
            self.drift.append(dict(observation))
            self.drift = self.drift[-8:]

    # -- rendering ---------------------------------------------------------

    def _state_unlocked(self) -> tuple[str, str | None]:
        if self.stopped_reason is not None:
            return "stopped", self.stopped_reason
        if not self.chain_ok:
            return "stopped", self.chain_reason
        if self.clock_skew_s is not None:
            return "degraded", "clock-skew"
        if not self.self_test_passing:
            return "degraded", "redaction-self-test-failed"
        if self.export_last_error is not None:
            return "degraded", "export-error"
        if any(hook.errors for hook in self.hooks.values()):
            return "degraded", "hook-errors"
        if any(hook.installed and hook.last_fire_at is None for hook in self.hooks.values()):
            return "degraded", "hooks-never-fired"
        if self.gaps:
            return "degraded", "recording-gap"
        return "recording", None

    def to_dict(self) -> dict[str, Any]:
        """Return a consistent copy of the PRD 13 health payload."""
        with self._lock:
            state, reason = self._state_unlocked()
            now = datetime.now(timezone.utc)
            uptime = max(0.0, (now - self.started_at).total_seconds())
            return {
                "state": state,
                "reason": reason,
                "daemon": {"pid": self.pid, "uptime_s": uptime, "version": self.version},
                "store": {
                    "path": self.store_path,
                    "records": self.records,
                    "size_mb": round(self.size_bytes / _BYTES_PER_MB, 3),
                    "chain_ok": self.chain_ok,
                    "durability": self.durability,
                    "last_append_at": _iso(self.last_append_at),
                },
                "export": {
                    "enabled": self.export_enabled,
                    "endpoint": self.export_endpoint,
                    "last_success_at": _iso(self.export_last_success_at),
                    "last_error": self.export_last_error,
                },
                "redaction": {
                    "mode": self.redaction_mode,
                    "self_test_passing": self.self_test_passing,
                },
                "signing": self._signing_payload(),
                "hooks": {name: hook.to_dict() for name, hook in self.hooks.items()},
                "gaps": list(self.gaps),
                "drift": list(self.drift),
                "clock_skew_s": self.clock_skew_s,
            }

    def _signing_payload(self) -> dict[str, Any]:
        """Whether this installation holds a signing key (no key material leaked)."""
        from agentwatch.signing import KEY_FILENAME, SigningError, load_or_create_key

        path = Path(self.store_path).parent / KEY_FILENAME
        if not path.exists():
            return {"configured": False, "key_id": None, "key_present": False}
        try:
            key = load_or_create_key(path)
        except SigningError:
            return {"configured": True, "key_id": None, "key_present": False}
        return {"configured": True, "key_id": key.key_id, "key_present": True}


def local_snapshot(
    *,
    store: RecordStore,
    version: str | None = None,
    hooks_installed: bool = False,
    export_enabled: bool = False,
    export_endpoint: str | None = None,
    redaction_mode: str = "metadata-only",
    self_test_passing: bool = True,
    reason: str = _STOPPED_REASON,
    durability: str | None = None,
) -> HealthSnapshot:
    """Build a stopped snapshot from local state (the daemon is not serving)."""
    snapshot = HealthSnapshot(
        store_path=store.path,
        version=version,
        export_enabled=export_enabled,
        export_endpoint=export_endpoint,
        redaction_mode=redaction_mode,
        self_test_passing=self_test_passing,
        hooks_installed=hooks_installed,
        durability=durability if durability is not None else store.durability,
    )
    snapshot.set_chain(store.verify())
    snapshot.set_store_stats(
        records=len(store.records()),
        size_bytes=store.size_bytes(),
    )
    snapshot.set_stopped(reason)
    return snapshot


def parse_endpoint(endpoint: str) -> tuple[str, int]:
    """Split ``host:port`` (defaulting the host to loopback and the port to 9100)."""
    host, sep, port_text = endpoint.rpartition(":")
    if not sep:
        return "127.0.0.1", 9100
    if host in {"", "0.0.0.0", "::"}:
        host = "127.0.0.1"
    try:
        port = int(port_text)
    except ValueError:
        port = 9100
    return host, port


class _HealthHandler(BaseHTTPRequestHandler):
    """Serve ``/healthz`` from the snapshot attached to the server."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
        """Silence the default per-request stderr logging."""

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] != HEALTH_PATH:
            self.send_error(404, "not found")
            return
        server = cast("_HealthServer", self.server)
        body = json.dumps(server.snapshot.to_dict()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _HealthServer(ThreadingHTTPServer):
    """ThreadingHTTPServer carrying the snapshot for the handler."""

    daemon_threads = True

    def __init__(self, address: tuple[str, int], snapshot: HealthSnapshot) -> None:
        self.snapshot = snapshot
        super().__init__(address, _HealthHandler)


class HealthServer:
    """Loopback-only health HTTP server, started/stopped explicitly."""

    def __init__(self, snapshot: HealthSnapshot, endpoint: str = "127.0.0.1:9100") -> None:
        host, port = parse_endpoint(endpoint)
        if host not in _LOOPBACK_HOSTS:
            host = "127.0.0.1"
        self._server = _HealthServer((host, port), snapshot)
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)


def start_health_server(
    snapshot: HealthSnapshot, endpoint: str = "127.0.0.1:9100"
) -> HealthServer | None:
    """Start the health server; return ``None`` (never raise) when unavailable.

    Port-in-use and bind errors are logged and swallowed: health is best-effort
    and recording must continue (PRD 22 B1).
    """
    try:
        server = HealthServer(snapshot, endpoint)
        server.start()
    except OSError as exc:
        print(
            f"agentwatch-daemon: health endpoint unavailable ({endpoint}): {exc}",
            file=sys.stderr,
        )
        return None
    return server


def fetch_health(endpoint: str, *, timeout: float = 0.5) -> dict[str, Any] | None:
    """Fetch the health payload from a running daemon, or ``None`` if unreachable."""
    url = f"http://{endpoint}{HEALTH_PATH}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(payload, dict):
        return payload
    return None
