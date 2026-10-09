#!/usr/bin/env python3
"""PG-3: the unified store holds SDK spans alongside hook records, and the
integrity distinction is visible (hook = chain-protected, SDK = read-only)."""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from _ftutil import fail, ok, run  # noqa: E402


def main(argv: list[str]) -> int:
    run(["python3", "/ft/scripts/drive-agent.py", "--session", "ft-sdk"])
    run(["agentwatch", "verify-store"])
    rows = json.loads(run(["agentwatch", "union", "--json"]).stdout)
    hook = [r for r in rows if r.get("source") == "hook"]
    sdk = [r for r in rows if r.get("source") == "sdk"]
    if not hook:
        fail("union has no hook records")
    if not sdk:
        fail("union has no sdk spans (SDK records did not land in the store)")
    if not all(r.get("chain_protected") for r in hook):
        fail("a hook record is not chain-protected")
    if any(r.get("chain_protected") for r in sdk):
        fail("an sdk record is mislabelled chain-protected")
    ok(f"union: {len(hook)} chain-protected hook record(s), {len(sdk)} read-only sdk span(s); store verifies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
