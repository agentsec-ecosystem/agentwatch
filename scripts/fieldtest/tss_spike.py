#!/usr/bin/env python3
"""TSS-1: the TypeScript-spike deliverables are present and linked.

The spike's output is a decision, not an SDK: ADR-0049 records it (ship deferred
to v0.3.0), a round-trip contract test proves the portability premise, and the
WBS ticket tracks the result. This driver asserts all three; the contract test
itself is the shipped ``tests/test_ts_schema_portability.py`` (host assert).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from _ftutil import fail, ok  # noqa: E402

REPO = Path(os.environ.get("REPO_ROOT") or Path(__file__).resolve().parents[2])


def main(argv: list[str]) -> int:
    adr = REPO / "docs/adr/0049-typescript-sdk-decision.md"
    if not adr.is_file():
        fail("ADR-0049 (TypeScript SDK decision) is missing")
    adr_text = adr.read_text(encoding="utf-8")
    if "v0.3.0" not in adr_text:
        fail("ADR-0049 does not record the deferred (v0.3.0) ship decision")
    if "test_ts_schema_portability.py" not in adr_text:
        fail("ADR-0049 does not cite its round-trip contract test")

    contract = REPO / "tests/test_ts_schema_portability.py"
    if not contract.is_file():
        fail("round-trip contract test tests/test_ts_schema_portability.py is missing")

    wbs = REPO / "docs/wbs/v0.2.0/wbs-v0.2.0-part4-depth-release.md"
    if not wbs.is_file() or "TSS-1" not in wbs.read_text(encoding="utf-8"):
        fail("WBS does not track the TSS-1 spike (M28)")

    ok("TSS-1: ADR-0049 (ship deferred to v0.3.0) + round-trip contract test + WBS ticket present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
