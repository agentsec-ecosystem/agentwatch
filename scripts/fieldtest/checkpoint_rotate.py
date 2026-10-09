#!/usr/bin/env python3
"""CMP-3: key rotation is recorded as a metadata-only chain event, epoch-bound.

Rotates the signing key, then asserts the store actually carries a ``key-rotation``
chain record whose reported ``new_key_id`` matches the CLI's, and that the store
still verifies afterwards.
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, "/ft/scripts")
from _ftutil import fail, ok, records, run  # noqa: E402


def main(argv: list[str]) -> int:
    result = json.loads(run(["agentwatch", "checkpoint", "rotate", "--json"]).stdout)
    new_key_id = result.get("key_id")
    if not new_key_id:
        fail("`checkpoint rotate --json` reported no key id")

    run(["agentwatch", "verify-store"])

    events = [r for r in records() if (r.get("tool") or {}).get("name") == "key-rotation"]
    if not events:
        fail("no key-rotation chain event was recorded")
    last = events[-1]
    recorded = (last.get("tool") or {}).get("arguments", {}).get("new_key_id")
    if recorded != new_key_id:
        fail(f"recorded new_key_id {recorded!r} != reported {new_key_id!r}")

    ok(f"rotation recorded as chain event seq={result.get('seq')} (new key {new_key_id}); store verifies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
