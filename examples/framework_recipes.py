#!/usr/bin/env python3
"""Certified framework recipes (M29 FWK-1, PRD 51 §FWK-1, #446).

Prints the certified recipe set and, given a fixture, replays it through the shared
``agentwatch.ingest`` OTel transcoder — the same path a real framework's telemetry
takes. The frameworks are not installable in CI here, so the live pinned run is
BLOCKED and every row is tiered ``modeled``.

    python examples/framework_recipes.py
    python examples/framework_recipes.py --transcode adk
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agentwatch import frameworks
from agentwatch.ingest import transcode_otel_detailed

FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "packages"
    / "python-sdk"
    / "tests"
    / "fixtures"
    / "frameworks"
)


def render() -> str:
    lines = ["Certified framework recipes (FWK-1):"]
    for recipe in frameworks.all_recipes():
        lines.append(
            f"  {recipe.name:18} {recipe.package}=={recipe.pinned}  "
            f"[{recipe.source}, tier={recipe.tier}]"
        )
        for line in recipe.recipe.splitlines():
            lines.append(f"      {line}")
        if not recipe.live_verified:
            lines.append(f"      ! {recipe.blocked_reason}")
    return "\n".join(lines)


def transcode(name: str) -> dict[str, object]:
    fixture = json.loads((FIXTURES / name / "conformance.json").read_text(encoding="utf-8"))
    records, problems, unmapped = transcode_otel_detailed(fixture["input"], source=name)
    return {
        "records": [
            {"tool": record.tool.name, "step_type": record.step_type.value if record.step_type else None}
            for record in records
        ],
        "problems": [problem.reason for problem in problems],
        "unmapped": list(unmapped),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show the certified framework recipes.")
    parser.add_argument("--transcode", choices=frameworks.SUPPORTED_FRAMEWORKS)
    args = parser.parse_args(argv)
    if args.transcode:
        print(json.dumps(transcode(args.transcode), indent=2))
    else:
        print(render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
