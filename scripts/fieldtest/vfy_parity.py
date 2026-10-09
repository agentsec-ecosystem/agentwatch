#!/usr/bin/env python3
"""VFY-1: run the shipped browser-verifier differential test (single source of truth).

PRD VFY-1's condition -- the page opens from ``file://`` with **zero network
requests**, its verdicts **equal the CLI** on the whole fixture set, and a
tampered bundle **names the first broken link** -- is exactly
``packages/python-sdk/tests/test_browser_verifier.py``. That module is the
canonical implementation of the differential; this driver runs it under the same
interpreter that invoked the driver (so node + the SDK are on hand) rather than
re-implementing the check.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from _ftutil import ok  # noqa: E402

REPO = Path(os.environ.get("REPO_ROOT") or Path(__file__).resolve().parents[2])
TEST = "packages/python-sdk/tests/test_browser_verifier.py"


def main(argv: list[str]) -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO / "packages/python-sdk/src") + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TEST, "-q"],
        cwd=str(REPO),
        env=env,
    )
    if proc.returncode != 0:
        print("browser-verifier differential test failed", file=sys.stderr)
        return 1
    ok("browser verifier: offline, zero-network; verdicts equal CLI; tampered bundle names the first broken link")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
