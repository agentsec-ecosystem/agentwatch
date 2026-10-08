#!/usr/bin/env python3
"""M31 31.2 — cross-harness test-kit replay / self-test / cross-parser (XHT-1/2/3)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        run(["agentwatch", "ingest", "--format", "xht", "--self-test", "/ft/fixtures/xht"])
    elif "--opencode" in argv:
        run(["agentwatch", "ingest", "--format", "opencode", "--bounded", "/ft/fixtures/opencode"])
    else:
        run(["agentwatch", "ingest", "--format", "xht", "--cross-parser", "/ft/fixtures/xht"])
    ok("xht replay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
