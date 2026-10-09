#!/usr/bin/env python3
"""CCO-1: Claude Code native OTel ingest joins hook records by tool_use_id, and
``coverage`` surfaces the join string.

The join-rate and discrepancy-classification semantics are the shipped
``test_claude_otel.py`` (host assert); this driver proves the end-to-end ingest +
coverage path produces a real join in the recorder.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "/ft/scripts")
from _ftutil import arg, fail, fixture, ok, run  # noqa: E402


def main(argv: list[str]) -> int:
    corpus = Path(arg(argv, "--corpus") or fixture("cco"))
    run(["agentwatch", "ingest", "--format", "claude-otel", str(corpus)])

    report = json.loads(run(["agentwatch", "coverage", "--json"]).stdout)
    join = report.get("otel_join")
    if not join:
        fail("coverage reports no native telemetry join after claude-otel ingest")

    # The corpus is OTel-only, so the join line must carry the classified summary
    # form (join rate / discrepancy semantics are the shipped test_claude_otel.py).
    if not re.search(r"\d+ joined, \d+ hook-only, \d+ otel-only, \d+ discrepancies \(classified\)", join):
        fail(f"coverage join summary is not the classified form: {join!r}")

    run(["agentwatch", "verify-store"])
    ok(f"native OTel joined to hook records by tool_use_id ({join.strip()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
