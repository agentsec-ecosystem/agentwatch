#!/usr/bin/env python3
"""Capture real Claude Code hook events into the golden corpus (M8 addition I2).

Off the critical path: run this on a machine with an authenticated Claude Code
and live agentwatch hooks. It reads a JSONL stream of framed hook messages
(``{"phase": ..., "harness": "claude-code", "event": {...}}``), scrubs tool
content through the privacy pipeline, refuses to write if any secret survives,
and writes version-tagged fixtures under ``tests/fixtures/claude-code/golden/real/``.

Usage::

    agentwatch tail --json > hooks.jsonl   # or collect from the daemon spool
    python3 scripts/capture-golden.py --input hooks.jsonl --harness-version 2.0.14

Then review the diff and commit. Never commit unscrubbed captures.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentwatch.adapters.claude_code import normalize
from agentwatch.secrets import detect, redact_mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "packages/python-sdk/tests/fixtures/claude-code/golden/real"


def scrub(message: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``message`` with tool content redacted in place."""
    scrubbed = json.loads(json.dumps(message))
    event = scrubbed.get("event")
    if isinstance(event, dict):
        for key in ("tool_input", "tool_response"):
            if key in event:
                event[key], _ = redact_mapping(event[key])
    return scrubbed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="JSONL of framed hook messages")
    parser.add_argument("--harness-version", required=True, help="Claude Code version tag")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="corpus output directory")
    args = parser.parse_args(argv)

    out: Path = args.out.expanduser()
    out.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for index, line in enumerate(args.input.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        message = json.loads(line)
        fixture = {
            "harness_version": args.harness_version,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "message": scrub(message),
        }
        fixture["expected"] = [record.to_dict() for record in normalize(fixture["message"])]
        serialized = json.dumps(fixture, indent=2, sort_keys=True)
        if detect(serialized):
            print(
                f"refusing to write case {index}: secret survived scrubbing",
                file=sys.stderr,
            )
            return 1
        name = f"{index:03d}_{args.harness_version}.json"
        (out / name).write_text(serialized + "\n", encoding="utf-8")
        written.append(name)

    manifest = out / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "harness": "claude-code",
                "harness_version": args.harness_version,
                "captured_from_real_harness": True,
                "cases": written,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(written)} golden fixtures to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
