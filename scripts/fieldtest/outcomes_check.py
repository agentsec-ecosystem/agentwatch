#!/usr/bin/env python3
"""OUT-1: outcome facts carry numerator/denominator + a derivation version
(was `grep numerator|denominator`)."""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, "/work/packages/python-sdk/src")
from _ftutil import fail, ok, run  # noqa: E402


def _facts(obj: object, out: list[dict]) -> None:
    if isinstance(obj, dict):
        if "numerator" in obj and "denominator" in obj:
            out.append(obj)
        for value in obj.values():
            _facts(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _facts(value, out)


def main(argv: list[str]) -> int:
    report = json.loads(run(["agentwatch", "outcomes", "--since", "30d", "--by", "project", "--json"]).stdout)
    version = report.get("derivation_version")
    if not version:
        fail("outcomes report has no derivation_version")
    facts: list[dict] = []
    _facts(report, facts)
    if not facts:
        fail("outcomes report has no numerator/denominator facts")
    ok(f"outcomes: {len(facts)} fact(s) with numerator/denominator; derivation_version={version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
