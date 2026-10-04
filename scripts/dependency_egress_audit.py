#!/usr/bin/env python3
"""Fail when the SDK source imports an egress-capable library (M12 K2, R6/NFR-9)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SDK = REPO / "packages" / "python-sdk"
sys.path.insert(0, str(SDK / "src"))

from agentwatch.egress_audit import audit  # noqa: E402


def main() -> int:
    findings = audit(SDK / "src")
    if findings:
        print("egress audit FAILED:")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print("egress audit: clean (no egress-capable imports)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
