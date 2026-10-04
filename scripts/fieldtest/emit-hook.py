#!/usr/bin/env python3
"""Emit hook frames through the real hook/socket path (M23 field tests).

Runs inside the recorder container. Like the production hook, a frame that
cannot be delivered is **spooled** (never dropped), so ``FT-16`` exercises the
same F1 path the daemon drains on restart.

Modes:
  --corpus secrets   secret-bearing attack pack (session ft04)
  --corpus partial   session-start + one call, no session-end (session ft-partial)
  --future           one record dated far in the future (clock-skew, session ft-future)
  --old              one record dated far in the past (crash-gap, session ft-old)
  --frames FILE      send each JSON frame in FILE (a JSON array or NDJSON)
  (no args)          read NDJSON frames from stdin

Secrets are built at runtime so no provider-shaped literal lives in the source.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/work/packages/python-sdk/src")
from agentwatch.hook import build_message, default_socket_path, send  # noqa: E402
from agentwatch.spool import Spool  # noqa: E402


def _frame(phase: str, session: str, tool: str, *, call: str, extra: dict) -> dict:
    event = {"session_id": session, "tool_name": tool, "tool_use_id": call, **extra}
    return build_message(phase, event)


def secret_corpus(session: str = "ft04") -> list[dict]:
    api_key = "sk-" + "abcdefghijklmnop"
    card = "4111 1111 1111 1111"
    dsn = "postgres://user:" + "pgLEAK" + "@db:5432/app"
    email = "leaker@example.com"
    return [
        _frame(
            "pre",
            session,
            "Bash",
            call="c1",
            extra={"tool_input": {"command": f"curl -H 'x-api-key: {api_key}' https://x"}},
        ),
        _frame("post", session, "Bash", call="c1", extra={"duration_ms": 12}),
        _frame(
            "pre", session, "Bash", call="c2", extra={"tool_input": {"command": f"psql {dsn}"}}
        ),
        _frame("post", session, "Bash", call="c2", extra={"duration_ms": 5}),
        _frame(
            "pre",
            session,
            "Write",
            call="c3",
            extra={"tool_input": {"path": "/tmp/card.txt", "content": card}},
        ),
        _frame("prompt", session, "user-prompt", call="c4", extra={"prompt": f"email {email}"}),
    ]


def partial_corpus(session: str = "ft-partial") -> list[dict]:
    """A session that starts and makes a call, but never ends (F10)."""
    return [
        _frame("session-start", session, "session-start", call="s0", extra={"cwd": "/work"}),
        _frame(
            "pre",
            session,
            "Bash",
            call="p1",
            extra={"tool_input": {"command": "echo partial"}},
        ),
    ]


def dated_frame(session: str, when: str) -> list[dict]:
    return [
        _frame(
            "pre",
            session,
            "Bash",
            call="t1",
            extra={"tool_input": {"command": "date"}, "timestamp": when},
        )
    ]


def _load_frames(path: str) -> list[dict]:
    text = open(path, encoding="utf-8").read()  # noqa: SIM115
    stripped = text.strip()
    if stripped.startswith("["):
        data = json.loads(stripped)
        return [item for item in data if isinstance(item, dict)]
    return [json.loads(line) for line in stripped.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", default=None)
    parser.add_argument("--corpus", choices=("secrets", "partial"), default=None)
    parser.add_argument("--future", action="store_true")
    parser.add_argument("--old", action="store_true")
    parser.add_argument("--session", default="ft04")
    args = parser.parse_args(argv)

    socket_path = os.environ.get("AGENTWATCH_SOCKET") or default_socket_path()
    if args.corpus == "secrets":
        frames = secret_corpus(args.session)
    elif args.corpus == "partial":
        frames = partial_corpus(args.session)
    elif args.future:
        frames = dated_frame("ft-future", "2099-01-01T00:00:00+00:00")
    elif args.old:
        # 10 minutes in the past: older than the 300 s gap threshold, but recent
        # enough that retention does not tombstone it before gap detection.
        past = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
        frames = dated_frame("ft-old", past)
    elif args.frames:
        frames = _load_frames(args.frames)
    else:
        frames = [json.loads(line) for line in sys.stdin if line.strip()]

    delivered = 0
    spooled = 0
    spool = Spool(socket_path + ".spool")
    for frame in frames:
        if send(frame, socket_path=socket_path):
            delivered += 1
        else:
            # Same F1 behavior as the production hook: spool, never drop.
            spool.append(frame)
            spooled += 1
    print(
        f"emit-hook: {delivered} delivered, {spooled} spooled "
        f"({len(frames)} frames) -> {socket_path}"
    )
    return 0 if delivered + spooled == len(frames) else 1


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
