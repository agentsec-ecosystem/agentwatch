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
import socket
import threading
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentwatch.adapters import claude_code
from agentwatch.adapters.claude_code import ClaudeCodeAdapterError
from agentwatch.hook import default_socket_path
from agentwatch.records import AgentRecord, Outcome, StepType, ToolCall, _parse_iso
from agentwatch.redact import RedactionConfig

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
        redaction: RedactionConfig | None = None,
        pre_timeout_seconds: float = 300.0,
        sweep_interval_seconds: float = 5.0,
    ) -> None:
        self.socket_path = (
            Path(socket_path) if socket_path is not None else Path(default_socket_path())
        )
        self.records_path = (
            Path(records_path) if records_path is not None else default_records_path()
        )
        self.redaction = redaction
        self.pre_timeout_seconds = pre_timeout_seconds
        self.sweep_interval_seconds = sweep_interval_seconds
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._sweeper: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._owns_socket = False
        # Pre tool-call ids awaiting their Post, for F2 hook-error synthesis.
        self._pending_pre: dict[str, datetime] = {}

    def is_alive(self) -> bool:
        """Whether the serve thread is running."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Bind the socket (0600) and start serving in a background thread."""
        self.records_path.parent.mkdir(parents=True, exist_ok=True)
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
            return
        self.handle_message(message)

    def handle_message(self, message: Any) -> list[AgentRecord]:
        """Normalize and persist a message; unsupported messages yield nothing."""
        if not isinstance(message, Mapping):
            return []

        phase = message.get("phase")
        event = message.get("event")

        if phase == "hook-error":
            record = self._hook_error_record(event)
            self._append(record)
            self._sweep_pending_pre()
            return [record]

        if phase not in ("pre", "post"):
            return []

        try:
            records = claude_code.normalize(message, redaction=self.redaction)
        except (ClaudeCodeAdapterError, ValueError, TypeError, KeyError):
            # A recognized phase that fails to normalize is a missed call: record it.
            record = self._hook_error_record(event)
            self._append(record)
            self._sweep_pending_pre()
            return [record]

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

        self._sweep_pending_pre()
        for record in records:
            self._append(record)
        return records

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
            agent=claude_code.identity_from(raw.get("agent")),
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

    def _append(self, record: AgentRecord) -> None:
        with self._lock, self.records_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict()) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the daemon until interrupted."""
    daemon = Daemon()
    daemon.start()
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:  # pragma: no cover - interactive shutdown
        return 0
    finally:
        daemon.stop()
