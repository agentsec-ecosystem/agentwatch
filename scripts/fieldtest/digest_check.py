#!/usr/bin/env python3
"""OUT-2: the digest is derived with a versioned grouping and pattern counts
(was `agentwatch digest --since 30d` exit 0)."""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, "/work/packages/python-sdk/src")
from _ftutil import fail, ok  # noqa: E402

from agentwatch.digest import SIGNATURES_VERSION, build_digest  # noqa: E402
from agentwatch.store import RecordStore  # noqa: E402


def main(argv: list[str]) -> int:
    store = RecordStore("/data/agentwatch/records.jsonl")
    report = build_digest(store, since="30d")
    if report.signatures_version != SIGNATURES_VERSION:
        fail(f"unexpected signatures_version {report.signatures_version!r}")
    bad = [
        p
        for p in report.signatures
        if getattr(p, "count", None) in (None, 0) or getattr(p, "first_seen", None) is None
    ]
    if bad:
        fail(f"{len(bad)} pattern(s) without count/first_seen")
    ok(f"digest: records={report.records}, signatures_version={report.signatures_version}, "
       f"patterns={len(report.signatures)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
