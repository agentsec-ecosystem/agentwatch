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
    ) -> None:
        self.socket_path = (
            Path(socket_path) if socket_path is not None else Path(default_socket_path())
        )
        self.records_path = (
            Path(records_path) if records_path is not None else default_records_path()
        )
        self.redaction = redaction
        self.pre_timeout_seconds = pre_timeout_seconds
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        # Pre tool-call ids awaiting their Post, for F2 hook-error synthesis.
        self._pending_pre: dict[str, datetime] = {}

    def start(self) -> None:
        """Bind the socket (0600) and start serving in a background thread."""
        self.records_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists():
            self.socket_path.unlink()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        server.listen(8)
        server.settimeout(0.2)
        self._server = server
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop serving, join the thread, and remove the socket file."""
        self._stop.set()
        if self._server is not None:
            self._server.close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        with contextlib.suppress(OSError):
            self.socket_path.unlink()

    def _serve(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                conn, _ = self._server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            with conn:
                self._read_connection(conn)

    def _read_connection(self, conn: socket.socket) -> None:
        conn.settimeout(1.0)
        buffer = b""
        try:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    self.handle_line(line)
        except OSError:  # pragma: no cover - peer closed mid-frame
            return

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

        if message.get("phase") == "hook-error":
            record = self._hook_error_record(message.get("event"))
            self._append(record)
            return [record]

        try:
            records = claude_code.normalize(message, redaction=self.redaction)
        except ClaudeCodeAdapterError:
            return []

        event = message.get("event")
        if not isinstance(event, Mapping):
            event = {}
        call_id = claude_code.tool_call_id(event)
        phase = message.get("phase")

        if phase == "pre" and call_id is not None:
            self._pending_pre[call_id] = datetime.now(timezone.utc)
        elif (
            phase == "post"
            and call_id is not None
            # A Post with no Pre means the intent hook was missed (F2).
            and self._pending_pre.pop(call_id, None) is None
        ):
            records.append(self._hook_error_record(event))

        self._sweep_pending_pre()
        for record in records:
            self._append(record)
        return records

    def _hook_error_record(self, event: Any) -> AgentRecord:
        raw: Mapping[str, Any] = event if isinstance(event, Mapping) else {}
        session_id = str(raw.get("session_id") or "unknown")
        call_id = claude_code.tool_call_id(raw)
        timestamp = raw.get("timestamp")
        started_at = (
            _parse_iso(timestamp) if isinstance(timestamp, str) else datetime.now(timezone.utc)
        )
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

    def _sweep_pending_pre(self) -> None:
        now = datetime.now(timezone.utc)
        stale = [
            call_id
            for call_id, seen in self._pending_pre.items()
            if (now - seen).total_seconds() > self.pre_timeout_seconds
        ]
        for call_id in stale:
            self._append(self._hook_error_record({"tool_use_id": call_id}))
            del self._pending_pre[call_id]

    def _append(self, record: AgentRecord) -> None:
        with self.records_path.open("a", encoding="utf-8") as fh:
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
