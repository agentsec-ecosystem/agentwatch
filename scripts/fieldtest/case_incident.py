#!/usr/bin/env python3
"""IR-1: multi-session incident case -- merged, ordered timeline + offline bundle.

Creates a case over the demo session, asserts the merged timeline states its
ordering rule and is actually ordered by it, then exports a case bundle and
re-verifies it offline. Gap classification is the shipped ``test_incident_cases.py``
(host assert).
"""

from __future__ import annotations

import json
import sys
import tempfile

sys.path.insert(0, "/ft/scripts")
from _ftutil import fail, ok, run  # noqa: E402


def main(argv: list[str]) -> int:
    store_dir = tempfile.mkdtemp(prefix="ir1-")
    base = ["agentwatch", "--set", f"store.path={store_dir}"]
    run([*base, "demo"])

    case = json.loads(
        run([*base, "case", "create", "--title", "INC-4471", "--severity", "high",
             "--ref", "INC-4471", "--json"]).stdout
    )
    case_id = case["case_id"]
    run([*base, "case", "add", case_id, "--session", "demo"])

    timeline = json.loads(run([*base, "case", "show", case_id, "--json"]).stdout)
    if not timeline.get("ordering"):
        fail("case timeline states no ordering rule")
    entries = timeline.get("entries") or []
    if not entries:
        fail("case timeline has no entries for the member session")
    ats = [entry["at"] for entry in entries]
    if ats != sorted(ats):
        fail("case timeline entries are not ordered by the stated rule ('at')")
    if not isinstance(timeline.get("gaps"), list):
        fail("case timeline does not carry a gaps list")

    run([*base, "case", "export", case_id, "--out", "/tmp/case.zip"])
    run(["agentwatch", "case", "verify", "/tmp/case.zip"])

    ok(f"incident case {case_id}: {len(entries)} ordered entries; offline bundle verifies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
