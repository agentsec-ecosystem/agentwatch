#!/usr/bin/env python3
"""M31 31.2 — multi-session incident case: create → show → export (IR-1).

`case create` auto-assigns the case id (``C<n>``); it is not a positional, so the
driver creates the case, reads the id back, then shows/exports that id.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv: list[str]) -> int:
    proc = run(["agentwatch", "case", "create", "--title", "INC-4471",
                "--severity", "high", "--ref", "INC-4471", "--json"])
    cid = json.loads(proc.stdout)["case_id"]
    run(["agentwatch", "case", "show", cid, "--json"])
    run(["agentwatch", "case", "export", cid, "--out", "/tmp/case.zip"])
    ok(f"incident case {cid} created, shown, exported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
