#!/usr/bin/env python3
"""AGI-2: the investigation skill reaches its documented answers on a demo store.

Seeds the synthetic ``demo`` session into an isolated temp store and drives the
commands the shipped skill documents (SKILL.md -> "Documented answers on the demo
store"), asserting the exact counts it promises. Runs the *installed* CLI in the
recorder, so it exercises the image, not the host.
"""

from __future__ import annotations

import json
import sys
import tempfile

sys.path.insert(0, "/ft/scripts")
from _ftutil import fail, ok, run  # noqa: E402


def main(argv: list[str]) -> int:
    store_dir = tempfile.mkdtemp(prefix="agi2-demo-")
    base = ["agentwatch", "--set", f"store.path={store_dir}"]

    run([*base, "demo"])

    sessions = run([*base, "sessions"]).stdout
    if "demo" not in sessions:
        fail("`sessions` does not list the demo session the skill documents")

    lines = [
        line
        for line in run([*base, "search", "--session", "demo", "--json"]).stdout.splitlines()
        if line.strip()
    ]
    if len(lines) != 6:
        fail(f"`search --session demo --json` returned {len(lines)} record lines (skill documents 6)")

    replay = json.loads(run([*base, "replay", "demo", "--json"]).stdout)
    if len(replay) != 6 or not all("record" in item for item in replay):
        fail("`replay demo --json` is not 6 ordered {record} items")

    impact = json.loads(run([*base, "impact", "demo", "--json"]).stdout)
    if impact.get("records") != 6 or not impact.get("denials"):
        fail(
            f"`impact demo --json` records={impact.get('records')} "
            f"denials={impact.get('denials')} (skill documents 6 with a denial)"
        )

    ok("investigation skill: demo-store answers match the skill (6 records; replay 6; impact 6 with a denial)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
