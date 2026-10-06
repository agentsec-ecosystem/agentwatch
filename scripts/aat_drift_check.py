#!/usr/bin/env python3
"""AAT draft-revision drift check (M26 AAT-5, #315).

Compares the pinned IETF Agent Audit Trail revision (and the fields we map)
against an upstream descriptor, so the draft moving on its fast cadence is
surfaced instead of silently changing our output. A revision bump, or an
upstream field we map that has disappeared, is a failure; a brand-new upstream
field is informational only.

Usage::

    python scripts/aat_drift_check.py upstream.json [--json]

where ``upstream.json`` is ``{"revision": "draft-sharif-agent-audit-trail-07",
"fields": ["agent", "action_type", ...]}``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from agentwatch.aat import check_aat_drift
except ImportError:  # pragma: no cover - guidance when run without the SDK
    sys.path.insert(
        0, str(Path(__file__).resolve().parent.parent / "packages" / "python-sdk" / "src")
    )
    from agentwatch.aat import check_aat_drift


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in args
    paths = [arg for arg in args if arg != "--json"]
    if not paths:
        print("usage: aat_drift_check.py UPSTREAM.json [--json]", file=sys.stderr)
        return 2
    try:
        upstream = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"aat-drift: cannot read upstream: {exc}", file=sys.stderr)
        return 2
    report = check_aat_drift(upstream)
    if as_json:
        print(json.dumps(report.to_dict(), sort_keys=True))
    if report.drifted:
        if report.pinned != report.upstream:
            print(
                f"aat-drift: upstream moved {report.pinned} -> {report.upstream}; "
                "re-pin or record the move (docs/design/aat-mapping.md)",
                file=sys.stderr,
            )
        else:
            print(
                f"aat-drift: pinned {report.pinned} is missing {', '.join(report.missing)}",
                file=sys.stderr,
            )
        return 1
    print(f"aat-drift: ok (pinned {report.pinned}, extra={list(report.extra)})")
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
