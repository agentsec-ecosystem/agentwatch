#!/usr/bin/env python3
"""ACC-2: every governance-notice statement is backed by a config key (or a
documented guarantee), and the not-legal-advice banner is present (was a banner grep)."""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, "/work/packages/python-sdk/src")
from _ftutil import fail, ok, run  # noqa: E402

from agentwatch.governance import known_config_keys  # noqa: E402


def main(argv: list[str]) -> int:
    payload = json.loads(run(["agentwatch", "governance", "notice", "--json"]).stdout)
    notice = payload.get("notice", payload)
    statements = notice.get("statements") or []
    if not statements:
        fail("governance notice has no statements")
    keys = known_config_keys()
    unbacked = [
        s
        for s in statements
        if not s.get("backing")
        or (s["backing"] not in keys and "guarantee" not in str(s["backing"]).lower())
    ]
    if unbacked:
        fail(f"{len(unbacked)} statement(s) not backed by a config key/guarantee: {unbacked[:2]}")
    if "not legal advice" not in str(notice.get("banner", "")).lower():
        fail("notice is missing the 'not legal advice' banner")
    ok(f"governance notice: {len(statements)} backed statement(s); not-legal-advice banner present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
