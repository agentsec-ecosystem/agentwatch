#!/usr/bin/env python3
"""PG-1: the embedded index rebuilds **bit-for-bit** (same output, same bytes)."""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from _ftutil import fail, ok, run  # noqa: E402

INDEX = Path("/data/agentwatch/index.sqlite3")


def _rebuild() -> tuple[str, str]:
    out = run(["agentwatch", "index", "rebuild", "--json"]).stdout.strip()
    digest = hashlib.sha256(INDEX.read_bytes()).hexdigest() if INDEX.exists() else ""
    return out, digest


def main(argv: list[str]) -> int:
    first, first_hash = _rebuild()
    second, second_hash = _rebuild()
    if first != second:
        fail(f"index rebuild output differs between runs:\n{first}\n{second}")
    if not first_hash or first_hash != second_hash:
        fail(f"index is not bit-for-bit (sha256 {first_hash[:12] or 'none'} != {second_hash[:12] or 'none'})")
    ok(f"index rebuild is bit-for-bit (sha256={first_hash[:12]}…, output identical)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
