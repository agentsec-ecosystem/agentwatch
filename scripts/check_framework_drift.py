#!/usr/bin/env python3
"""Framework-recipe drift canary (M29 FWK-1 #446).

The certified recipe set pins one framework version each. A framework release can
rename or add an OTel attribute; the fixture conformance pack catches the shape,
but only if someone knows to look. This job compares the pinned versions against
the recorded upstream manifest and fails loudly when they diverge, so the drift is
surfaced for a human rather than discovered by a user.

It never edits anything: a scheduled run opens an issue (see
``.github/workflows/framework-drift.yml``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SDK = REPO / "packages" / "python-sdk"
sys.path.insert(0, str(SDK / "src"))

from agentwatch import frameworks  # noqa: E402

MANIFEST = SDK / "tests" / "fixtures" / "frameworks" / "upstream.json"


def load_upstream(path: Path = MANIFEST) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    entries = data.get("frameworks") if isinstance(data, dict) else None
    if not isinstance(entries, dict):
        return {}
    return {str(key): str(value) for key, value in entries.items()}


def check(path: Path = MANIFEST) -> list[str]:
    return frameworks.drift(load_upstream(path))


def main() -> int:
    drift = check()
    if drift:
        print("framework recipe drift detected:")
        for entry in drift:
            print(f"  - {entry}")
        return 1
    print(f"framework recipes are at their pinned upstream versions ({len(frameworks.RECIPES)}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
