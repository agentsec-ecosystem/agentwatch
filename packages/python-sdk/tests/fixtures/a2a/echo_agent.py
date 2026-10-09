"""Tiny A2A-ish stdio server for proxy tests (echoes task results)."""

import json
import sys


def main() -> int:
    for line in sys.stdin.buffer:
        try:
            message = json.loads(line)
        except ValueError:
            sys.stdout.buffer.write(line)  # echo garbage unchanged
            sys.stdout.buffer.flush()
            continue
        if not isinstance(message, dict):
            continue
        method = message.get("method")
        if method in ("message/send", "message/stream"):
            params = message.get("params", {})
            msg = params.get("message", {}) if isinstance(params, dict) else {}
            reply = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "kind": "task",
                    "id": msg.get("taskId", "t-1"),
                    "status": {"state": "completed"},
                },
            }
        elif method == "tasks/get":
            reply = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {"kind": "task", "id": "t-1", "status": {"state": "working"}},
            }
        else:
            reply = {"jsonrpc": "2.0", "id": message.get("id"), "result": {}}
        sys.stdout.buffer.write(json.dumps(reply).encode() + b"\n")
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())