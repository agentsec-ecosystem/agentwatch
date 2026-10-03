"""Claude Code hook client (M3 #25).

`agentwatch-hook pre|post` reads a Claude Code event JSON from stdin, frames it as
one newline-delimited JSON message, and sends it to the daemon over a Unix domain
socket. It is **fire-and-forget**: it always exits 0 so a hook can never block or
fail the agent (F2). A missed delivery is reported by the daemon path (M3 3.7).
"""

from __future__ import annotations

import json
import os
import socket
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

_SOCKET_NAME = "agentwatch.sock"
_VALID_PHASES = ("pre", "post", "session-start", "session-end")
_CONNECT_TIMEOUT_SECONDS = 1.0


def default_socket_path() -> str:
    """Resolve the daemon socket: ``$AGENTWATCH_SOCKET``, then XDG, then ``/tmp``."""
    explicit = os.environ.get("AGENTWATCH_SOCKET")
    if explicit:
        return explicit
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    base = Path(runtime) if runtime else Path("/tmp")
    return str(base / _SOCKET_NAME)


def build_message(phase: str, event: Any) -> dict[str, Any]:
    """Frame a hook event as the daemon-expected message."""
    return {"phase": phase, "harness": "claude-code", "event": event}


def send(message: dict[str, Any], *, socket_path: str | None = None) -> bool:
    """Send one framed message; return whether it was delivered (never raises)."""
    path = socket_path or default_socket_path()
    payload = json.dumps(message).encode("utf-8") + b"\n"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(_CONNECT_TIMEOUT_SECONDS)
        sock.connect(path)
        sock.sendall(payload)
        return True
    except OSError:
        return False
    finally:
        sock.close()


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    socket_path: str | None = None,
) -> int:
    """Run the hook. Always returns 0 (fire-and-forget)."""
    args = list(sys.argv[1:] if argv is None else argv)
    stream = sys.stdin if stdin is None else stdin
    try:
        raw = stream.read()
    except OSError:  # pragma: no cover - stdin read failure is environment-specific
        raw = ""

    try:
        event: Any = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        event = None

    phase = args[0] if args else ""
    if phase in _VALID_PHASES:
        if event is not None:
            send(build_message(phase, event), socket_path=socket_path)
        else:
            # F2: report the malformed input so the missed call is recorded, not dropped.
            send(
                build_message("hook-error", {"reason": "malformed hook input"}),
                socket_path=socket_path,
            )

    # Never block the agent: a missed event is the daemon's to record (M3 3.7).
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
