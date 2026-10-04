#!/usr/bin/env python3
"""Semconv drift check (M22 W4, #273).

Compares the pinned OTel GenAI attribute set against an upstream set (a JSON
array of attribute names, e.g. captured from the semconv repository) and opens
visibility on drift instead of breaking silently. An upstream attribute that we
emit but that has disappeared is a failure; a brand-new upstream attribute is
informational only.

Usage::

    python scripts/semconv_drift_check.py upstream-attributes.json [--json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from agentwatch.semconv import check_drift
except ImportError:  # pragma: no cover - guidance when run without the SDK
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "python-sdk" / "src"))
    from agentwatch.semconv import check_drift


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in args
    paths = [arg for arg in args if arg != "--json"]
    if not paths:
        print("usage: semconv_drift_check.py UPSTREAM.json [--json]", file=sys.stderr)
        return 2
    try:
        upstream = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"semconv-drift: cannot read upstream: {exc}", file=sys.stderr)
        return 2
    if not isinstance(upstream, list):
        print("semconv-drift: upstream must be a JSON array of attribute names", file=sys.stderr)
        return 2
    report = check_drift([str(item) for item in upstream])
    if as_json:
        print(json.dumps(report.to_dict(), sort_keys=True))
    if report.drifted:
        print(
            f"semconv-drift: pinned {report.version} is missing {', '.join(report.missing)}",
            file=sys.stderr,
        )
        return 1
    print(f"semconv-drift: ok (pinned {report.version}, extra={list(report.extra)})")
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
