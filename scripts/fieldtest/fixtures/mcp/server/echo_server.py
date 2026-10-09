"""Tiny MCP-ish stdio server for proxy tests (echoes tools/call results)."""

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
        if message.get("method") == "tools/call":
            reply = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {"echo": message.get("params", {}).get("name")},
            }
        else:
            reply = {"jsonrpc": "2.0", "id": message.get("id"), "result": {}}
        sys.stdout.buffer.write(json.dumps(reply).encode() + b"\n")
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
