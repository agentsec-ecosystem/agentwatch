#!/usr/bin/env python3
"""CMP-2: the signed default posture is verifiable end-to-end.

Exports a signed checkpoint, re-verifies the store, and asserts ``doctor`` surfaces
the signing posture (key id + epoch) rather than hiding an unverifiable key. The
tamper and missing-key cases are the shipped ``test_signing_posture.py`` (run as a
host assert), so this driver stays on the live happy path.
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, "/ft/scripts")
from _ftutil import fail, ok, run  # noqa: E402


def main(argv: list[str]) -> int:
    run(["agentwatch", "checkpoint", "export", "--sign", "--output", "/tmp/cp.json"])
    run(["agentwatch", "verify-store"])

    doctor = json.loads(run(["agentwatch", "doctor", "--json"]).stdout)
    checks = {c.get("name"): c for c in doctor.get("checks", [])}
    signing = checks.get("signing")
    if signing is None:
        fail("`doctor --json` carries no signing check")
    if str(signing.get("status", "")).upper() != "PASS":
        fail(f"signing check is not PASS: {signing}")
    detail = str(signing.get("detail", ""))
    if "epoch" not in detail.lower():
        fail(f"signing detail does not name the key id/epoch: {detail!r}")

    ok(f"signed default: store verifies; doctor signing = {signing['status']} ({detail})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
