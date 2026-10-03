"""agentwatch daemon: hook frames -> normalized records (M3 #26).

The daemon listens on a Unix domain socket (owner-only, 0600), receives
newline-delimited JSON hook messages, normalizes them through the Claude Code
adapter, and appends validated records to a JSONL sink. Malformed input is
isolated to its line and never kills the daemon.

The M4 store replaces the plain JSONL sink with the hash-chained local store
(R11); M3 uses the file sink deliberately.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import socket
import sys
import threading
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentwatch.adapters import claude_code
from agentwatch.adapters.claude_code import ClaudeCodeAdapterError
from agentwatch.health import (
    HealthServer,
    HealthSnapshot,
    start_health_server,
)
from agentwatch.hook import default_socket_path
from agentwatch.quarantine import QuarantineLog
from agentwatch.records import AgentRecord, Outcome, StepType, ToolCall, _parse_iso
from agentwatch.redact import RedactionConfig
from agentwatch.spool import Spool
from agentwatch.store import ChainStatus, RecordStore, StoreFullError
from agentwatch.transcript import extract_usage

# F2: a missed tool call is recorded under this tool name, never dropped.
HOOK_ERROR_TOOL = "hook-error"


def default_records_path() -> Path:
    """Resolve the JSONL sink from the PRD 16 config ``store.path``."""
    from agentwatch.configuration import load_config

    return Path(load_config().store.path).expanduser() / "records.jsonl"


class Daemon:
    """Serve the hook socket and persist normalized records."""

    def __init__(
        self,
        *,
        socket_path: str | os.PathLike[str] | None = None,
        records_path: str | os.PathLike[str] | None = None,
        store: RecordStore | None = None,
        retention_days: int | None = None,
        redaction: RedactionConfig | None = None,
        pre_timeout_seconds: float = 300.0,
        sweep_interval_seconds: float = 5.0,
        gap_threshold_seconds: float = 300.0,
        health: HealthSnapshot | None = None,
        health_endpoint: str | None = None,
    ) -> None:
        self.socket_path = (
            Path(socket_path) if socket_path is not None else Path(default_socket_path())
        )
        self.records_path = (
            Path(records_path) if records_path is not None else default_records_path()
        )
        self.store = store if store is not None else RecordStore(self.records_path)
        self.retention_days = retention_days
        self.gap_threshold_seconds = gap_threshold_seconds
        self.pid_path = self.records_path.parent / "daemon.pid"
        self.quarantine = QuarantineLog(self.records_path.parent / "quarantine.jsonl")
        self.spool = Spool(str(self.socket_path) + ".spool")
        self.chain_status: ChainStatus | None = None
        self.redaction = redaction
        self.pre_timeout_seconds = pre_timeout_seconds
        self.sweep_interval_seconds = sweep_interval_seconds
        self.health = (
            health
            if health is not None
            else HealthSnapshot(store_path=self.records_path)
        )
        self.health_endpoint = health_endpoint
        self._health_server: HealthServer | None = None
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._sweeper: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._owns_socket = False
        # Pre tool-call ids awaiting their Post, for F2 hook-error synthesis.
        self._pending_pre: dict[str, datetime] = {}
        # Idempotency keys already persisted, so re-delivery appends nothing (F2).
        self._seen: set[tuple[str, str | None, str | None]] = set()

    def is_alive(self) -> bool:
        """Whether the serve thread is running."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def health_address(self) -> tuple[str, int] | None:
        """The bound health endpoint, or ``None`` when health is not serving."""
        return self._health_server.address if self._health_server is not None else None

    def start(self) -> None:
        """Bind the socket (0600) and start serving in a background thread."""
        self.records_path.parent.mkdir(parents=True, exist_ok=True)
        self.chain_status = self.store.verify()
        self.health.set_chain(self.chain_status)
        if not self.chain_status.ok:
            print(
                f"agentwatch-daemon: hash chain broken at seq {self.chain_status.broken_at} (F4)",
                file=sys.stderr,
            )
        if self.retention_days is not None:
            self.store.apply_retention(retention_days=self.retention_days)
        self._record_gap_if_needed()
        self._drain_spool()
        self._seen = {self._key(record) for record in self.store.records()}
        self.health.set_store_stats(
            records=len(self.store.records()), size_bytes=self.store.size_bytes()
        )
        self._prepare_socket_path()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        server.listen(8)
        server.settimeout(0.2)
        self._server = server
        self._owns_socket = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        self._sweeper = threading.Thread(target=self._sweep_loop, daemon=True)
        self._sweeper.start()
        if self.health_endpoint is not None:
            # Health is best-effort: a busy port logs and recording continues.
            self._health_server = start_health_server(self.health, self.health_endpoint)

    def _record_gap_if_needed(self) -> None:
        """Synthesize a recording-gap record after a crash (F1)."""
        if not self.pid_path.exists():
            return
        records = self.store.records()
        if not records:
            return
        last = records[-1]
        now = datetime.now(timezone.utc)
        gap_seconds = (now - last.started_at).total_seconds()
        if gap_seconds < self.gap_threshold_seconds:
            return
        gap = AgentRecord(
            session_id=last.session_id,
            agent=last.agent,
            tool=ToolCall(name="recording-gap", arguments={"reason": "daemon-restart"}),
            outcome=Outcome.ERROR,
            started_at=last.started_at,
            ended_at=now,
            duration_ms=gap_seconds * 1000.0,
            harness=claude_code.HARNESS_ID,
            trace_id=last.trace_id,
            step_type=StepType.ACT,
        )
        self._append(gap)
        self.health.note_gap({"reason": "daemon-restart", "at": now.isoformat()})

    def _prepare_socket_path(self) -> None:
        """Refuse to clobber a live daemon; replace a stale socket file."""
        if not self.socket_path.exists():
            return
        if self._is_live():
            raise RuntimeError(
                f"another agentwatch daemon is already listening on {self.socket_path}"
            )
        with contextlib.suppress(OSError):
            self.socket_path.unlink()

    def _is_live(self) -> bool:
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            probe.settimeout(0.2)
            probe.connect(str(self.socket_path))
            return True
        except OSError:
            return False
        finally:
            probe.close()

    def stop(self) -> None:
        """Stop serving, flush pending intents, and remove an owned socket."""
        self._stop.set()
        if self._health_server is not None:
            self._health_server.stop()
            self._health_server = None
        if self._server is not None:
            self._server.close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._sweeper is not None:
            self._sweeper.join(timeout=2)
        # Flush any unmatched intents so a missed Post is still recorded (F2).
        self._sweep_pending_pre(force=True)
        if self._owns_socket:
            with contextlib.suppress(OSError):
                self.socket_path.unlink()

    def _sweep_loop(self) -> None:
        while not self._stop.wait(self.sweep_interval_seconds):
            self._sweep_pending_pre()

    def _serve(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                conn, _ = self._server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            try:
                with conn:
                    self._read_connection(conn)
            except Exception:  # noqa: BLE001 - one bad connection must not kill the daemon
                continue

    def _read_connection(self, conn: socket.socket) -> None:
        conn.settimeout(1.0)
        buffer = b""
        while True:
            try:
                chunk = conn.recv(4096)
            except OSError:
                return
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                self.handle_line(line)

    def handle_line(self, line: bytes) -> None:
        """Handle one framed line; malformed lines are ignored, not fatal."""
        if not line.strip():
            return
        try:
            message = json.loads(line.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.quarantine.add(line, reason="malformed-line")
            return
        self.handle_message(message)

    def handle_message(self, message: Any) -> list[AgentRecord]:
        """Normalize and persist a message; unsupported messages yield nothing."""
        if not isinstance(message, Mapping):
            return []

        phase = message.get("phase")
        event = message.get("event")
        harness = str(message.get("harness") or claude_code.HARNESS_ID)

        if phase == "hook-error":
            self.health.note_hook_fire(harness)
            record = self._hook_error_record(event)
            persisted = self._append(record)
            self._sweep_pending_pre()
            return [record] if persisted else []

        if phase not in ("pre", "post", "denied", "prompt", "session-start", "session-end"):
            return []

        self.health.note_hook_fire(harness)
        try:
            records = claude_code.normalize(message, redaction=self.redaction)
        except (ClaudeCodeAdapterError, ValueError, TypeError, KeyError):
            # A recognized phase that fails to normalize is a missed call: record it,
            # and preserve the raw frame for diagnosis/reprocessing (F8).
            with contextlib.suppress(TypeError, ValueError):
                self.quarantine.add(json.dumps(message, default=str), reason="normalize-error")
            record = self._hook_error_record(event)
            persisted = self._append(record)
            self._sweep_pending_pre()
            return [record] if persisted else []

        if message.get("recovered"):
            records = [self._mark_recovered(record) for record in records]

        raw_event: Mapping[str, Any] = event if isinstance(event, Mapping) else {}
        call_id = claude_code.tool_call_id(raw_event)
        with self._lock:
            if phase == "pre" and call_id is not None:
                self._pending_pre[call_id] = datetime.now(timezone.utc)
            elif (
                phase == "post"
                and call_id is not None
                # A Post with no Pre means the intent hook was missed (F2).
                and self._pending_pre.pop(call_id, None) is None
            ):
                records.append(self._hook_error_record(raw_event))
            elif phase == "denied" and call_id is not None:
                # A denial retires the matching intent; no false hook-error.
                self._pending_pre.pop(call_id, None)

        if phase == "session-end":
            transcript_path = raw_event.get("transcript_path")
            if isinstance(transcript_path, str) and transcript_path:
                usage = extract_usage(transcript_path)
                records.append(
                    claude_code.usage_record(
                        raw_event, tokens=usage.tokens, model=usage.model
                    )
                )

        self._sweep_pending_pre()
        written: list[AgentRecord] = []
        for record in records:
            key = self._key(record)
            if key in self._seen:
                continue
            if self._append(record):
                self._seen.add(key)
                written.append(record)
        return written

    @staticmethod
    def _key(record: AgentRecord) -> tuple[str, str | None, str | None]:
        step = record.step_type.value if record.step_type is not None else None
        return (record.session_id, record.span_id, step)

    def _mark_recovered(self, record: AgentRecord) -> AgentRecord:
        arguments = record.tool.arguments
        merged = {**(arguments or {}), "recovered": True}
        return replace(record, tool=replace(record.tool, arguments=merged))

    def _drain_spool(self) -> None:
        """Persist frames spooled while the daemon was down (F1)."""
        for line in self.spool.drain():
            try:
                message = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                self.quarantine.add(line, reason="spool-parse-error")
                continue
            if isinstance(message, dict):
                message["recovered"] = True
            self.handle_message(message)

    def _hook_error_record(self, event: Any) -> AgentRecord:
        raw: Mapping[str, Any] = event if isinstance(event, Mapping) else {}
        session_id = str(raw.get("session_id") or "unknown")
        call_id = claude_code.tool_call_id(raw)
        started_at = datetime.now(timezone.utc)
        timestamp = raw.get("timestamp")
        if isinstance(timestamp, str):
            with contextlib.suppress(ValueError):
                started_at = _parse_iso(timestamp)
        return AgentRecord(
            session_id=session_id,
            agent=claude_code.identity_for(raw),
            tool=ToolCall(name=HOOK_ERROR_TOOL),
            outcome=Outcome.ERROR,
            started_at=started_at,
            harness=claude_code.HARNESS_ID,
            trace_id=session_id,
            span_id=call_id,
            step_type=StepType.ACT,
        )

    def _sweep_pending_pre(self, *, force: bool = False) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            stale = [
                call_id
                for call_id, seen in self._pending_pre.items()
                if force or (now - seen).total_seconds() > self.pre_timeout_seconds
            ]
            for call_id in stale:
                del self._pending_pre[call_id]
        for call_id in stale:
            self._append(self._hook_error_record({"tool_use_id": call_id}))

    def _append(self, record: AgentRecord) -> bool:
        """Persist one record; return False (never raise) when the store is full (F3)."""
        try:
            self.store.append(record)
        except StoreFullError as exc:
            # F3: fail closed and surface; never overwrite or drop silently.
            self.health.set_stopped(str(exc))
            print(f"agentwatch-daemon: {exc}", file=sys.stderr)
            return False
        self.health.record_appended(record, size_bytes=self.store.size_bytes())
        if record.tool.name == HOOK_ERROR_TOOL:
            self.health.note_hook_error(record.harness or claude_code.HARNESS_ID)
        return True


def main(argv: Sequence[str] | None = None) -> int:
    """Run the daemon until interrupted (SIGINT/SIGTERM stop it cleanly)."""
    from agentwatch.configuration import load_config
    from agentwatch.install import hooks_installed, resolve_scope
    from agentwatch.redact import PrivacyMode
    from agentwatch.selftest import run_redaction_self_test

    cfg = load_config()
    records_path = default_records_path()
    store = RecordStore(records_path, max_size_mb=cfg.store.max_size_mb)
    modes = {
        "metadata-only": PrivacyMode.METADATA_ONLY,
        "truncated": PrivacyMode.TRUNCATED,
        "hashed": PrivacyMode.HASHED,
        "full": PrivacyMode.FULL,
    }
    redaction = RedactionConfig(
        mode=modes.get(cfg.privacy.mode, PrivacyMode.METADATA_ONLY),
        capture_tool_args=True,
    )
    hooks_installed_any = any(
        hooks_installed(resolve_scope(scope).settings_path) for scope in ("project", "user")
    )
    health = HealthSnapshot(
        store_path=records_path,
        export_enabled=cfg.export.enabled,
        export_endpoint=cfg.export.otlp_endpoint,
        redaction_mode=cfg.privacy.mode,
        self_test_passing=run_redaction_self_test(redaction).passed,
        hooks_installed=hooks_installed_any,
    )
    daemon = Daemon(
        store=store,
        retention_days=cfg.store.retention_days,
        redaction=redaction,
        health=health,
        health_endpoint=cfg.health.endpoint,
    )
    daemon.start()
    stop = threading.Event()

    def _request_stop(signum: int, frame: object) -> None:  # pragma: no cover - signal path
        stop.set()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    try:
        while not stop.wait(1.0):
            pass
    finally:
        daemon.stop()
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
