#!/usr/bin/env python3
"""DEMO-1: the static synthetic demo bundle is offline-openable, marked synthetic,
and secret-free (was `json.tool` only)."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from _ftutil import fail, ok  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
BUNDLE = REPO / "examples/demo-bundle/bundle.json"
_SECRET = re.compile(r"sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----")


def main(argv: list[str]) -> int:
    text = BUNDLE.read_text(encoding="utf-8")
    data = json.loads(text)
    if data.get("bundle_format") != "agentwatch-demo/1":
        fail(f"unexpected bundle_format: {data.get('bundle_format')!r}")
    if data.get("synthetic") is not True:
        fail("demo bundle is not marked synthetic")
    if "never evidence" not in str(data.get("notice", "")).lower():
        fail("demo bundle is missing the 'never evidence' notice")
    match = _SECRET.search(text)
    if match:
        fail(f"demo bundle carries a secret-like string: {match.group(0)[:8]}…")
    ok("demo bundle: synthetic, secret-free, static (offline)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
