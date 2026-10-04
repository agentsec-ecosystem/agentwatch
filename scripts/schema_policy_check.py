#!/usr/bin/env python3
"""Schema stewardship policy check (M22 W5, #274).

Fails when a schema change has not moved with its changelog or the Python
vocabulary. Run in CI; see ``schema/GOVERNANCE.md``.

Usage::

    python scripts/schema_policy_check.py [SCHEMA_DIR]
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from agentwatch.schema_policy import check_schema_policy
except ImportError:  # pragma: no cover - guidance when run without the SDK
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "python-sdk" / "src"))
    from agentwatch.schema_policy import check_schema_policy


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    schema_dir = Path(args[0]) if args else Path(__file__).resolve().parent.parent / "schema"
    problems = check_schema_policy(schema_dir)
    for problem in problems:
        print(f"schema-policy: {problem}", file=sys.stderr)
    if problems:
        print(f"schema-policy: {len(problems)} violation(s)", file=sys.stderr)
        return 1
    print("schema-policy: ok")
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
