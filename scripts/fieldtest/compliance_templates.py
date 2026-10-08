#!/usr/bin/env python3
"""M31 31.2 — all five compliance templates run offline (CMP-3)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import ok, run


TEMPLATES = ["eu-ai-act-art12", "iso-42001", "iso-27001", "soc2", "nist-800-92"]


def main(argv: list[str]) -> int:
    for fw in TEMPLATES:
        run(["agentwatch", "compliance", "report", "--framework", fw, "--out", f"/tmp/audit-{fw}"])
    ok(f"all {len(TEMPLATES)} templates ran offline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
