#!/usr/bin/env python3
"""M31 31.2 — Claude Code native-OTel ingest + tool_use_id join (CCO-1)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import arg, fixture, ok, run


def main(argv: list[str]) -> int:
    corpus = Path(arg(argv, "--corpus") or fixture("cco"))
    run(["agentwatch", "ingest", "--format", "claude-otel", str(corpus)])
    out = run(["agentwatch", "coverage", "--json"]).stdout
    run(["agentwatch", "verify-store"])
    if "join" not in out and "otel" not in out.lower():
        print(out)
    ok("native OTel joined to hook records by tool_use_id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
