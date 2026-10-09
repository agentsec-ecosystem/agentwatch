#!/usr/bin/env python3
"""M31 31.2 — privacy-mode property test: no content leaks (OTEL-3, IDN-2)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import arg, ok, records, run


def main(argv: list[str]) -> int:
    run(["agentwatch", "verify-privacy"])
    what = arg(argv, "--what", "content")
    leaks: list[str] = []
    for r in records():
        tool = r.get("tool") or {}
        # Only captured *tool calls* carry user content; recorder control-plane
        # markers (privacy-mode-changed, retention-changed, …) legitimately carry
        # their own arguments and have no step_type.
        if (
            what == "content"
            and tool.get("privacy_mode") == "metadata-only"
            and r.get("step_type") in ("act", "observe")
            and (tool.get("arguments") or tool.get("response") or tool.get("content"))
        ):
            leaks.append(str(r.get("session_id")))
        if what == "identity" and (r.get("identity") or {}).get("secret"):
            leaks.append(str(r.get("session_id")))
    if leaks:
        print(f"leaks: {len(leaks)} ({what})", file=sys.stderr)
        return 1
    ok(f"privacy property holds for {what}: no metadata-only content across {len(records())} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
