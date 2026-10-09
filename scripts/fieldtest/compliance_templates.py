#!/usr/bin/env python3
"""CMP-3: all five compliance templates run offline and write a real report.

Each ``compliance report --framework ...`` must produce a non-empty artifact on
disk (not merely exit 0). The key-rotation chain event is asserted separately by
``checkpoint_rotate.py``; the shipped ``test_signing_posture.py`` (host assert) is
the canonical rotation test.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "/ft/scripts")
from _ftutil import fail, ok, run  # noqa: E402

TEMPLATES = ["eu-ai-act-art12", "iso-42001", "iso-27001", "soc2", "nist-800-92"]


def main(argv: list[str]) -> int:
    for framework in TEMPLATES:
        out = Path(f"/tmp/audit-{framework}")
        run(["agentwatch", "compliance", "report", "--framework", framework, "--out", str(out)])
        candidates = [out] if out.is_file() else [p for p in out.rglob("*") if p.is_file()]
        written = [p for p in candidates if p.stat().st_size > 0]
        if not written:
            fail(f"{framework}: no non-empty report written to {out}")
    ok(f"all {len(TEMPLATES)} compliance templates ran offline and wrote a report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
