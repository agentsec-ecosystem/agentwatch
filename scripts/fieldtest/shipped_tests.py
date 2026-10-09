#!/usr/bin/env python3
"""Run shipped pytest targets under the interpreter that invoked this driver.

Some plan conditions are already the subject of a shipped test in the repo (e.g.
the browser-verifier differential, the investigation-skill contract). Rather than
re-implement those checks in the field test, this driver runs the canonical test
module(s) with the SDK on ``PYTHONPATH`` and fails loudly if any do not pass, so a
field-test PASS is grounded on the shipped single source of truth.

Usage:
    python3 shipped_tests.py packages/python-sdk/tests/<file>.py [more ...]
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from _ftutil import fail, ok  # noqa: E402

REPO = Path(os.environ.get("REPO_ROOT") or Path(__file__).resolve().parents[2])

# Source roots that shipped tests import from (SDK + the services' src trees).
ROOTS = (
    "packages/python-sdk/src",
    "services/analytics/src",
    "services/api/src",
)


def main(argv: list[str]) -> int:
    targets = [arg for arg in argv if arg]
    if not targets:
        fail("no pytest targets given")
    env = dict(os.environ)
    parts = [str(REPO / root) for root in ROOTS]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *targets, "-q"],
        cwd=str(REPO),
        env=env,
    )
    if proc.returncode != 0:
        fail("shipped test(s) failed: " + " ".join(targets))
    ok("shipped test(s) passed: " + " ".join(targets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
