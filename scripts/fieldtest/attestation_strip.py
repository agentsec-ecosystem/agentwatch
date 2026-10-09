#!/usr/bin/env python3
"""DEP-2: a hook-configuration change between sessions must raise a
``recorder-config-changed`` observation, and the attestation must carry only
digests + booleans (never config values)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
for _cand in (
    "/work/packages/python-sdk/src",
    os.path.join(_HERE, "..", "..", "packages", "python-sdk", "src"),
):
    if os.path.isdir(_cand):
        sys.path.insert(0, _cand)

from agentwatch import attestation  # noqa: E402
from agentwatch.store import RecordStore  # noqa: E402

STORE = Path("/data/agentwatch/records.jsonl")


def main() -> int:
    store = RecordStore(STORE)
    # Session 1: hooks effective from the user scope.
    attestation.attest_session(store, user=True)
    # Session 2: the user hook was stripped -> the config digest moves.
    report = attestation.attest_session(store, user=False)

    text = STORE.read_text(encoding="utf-8")
    assert "recorder-config-changed" in text, "digest move did not raise recorder-config-changed"
    assert "config_digest" in text, "attestation carries no config_digest"
    assert report.marker is not None, "no session attestation recorded"
    assert report.config_changed is not None, "digest move did not return a config-changed marker"
    # Attestation is digest + booleans only: a real settings value must never appear.
    assert "allowManagedHooksOnly" not in text, "attestation leaked a config value"
    print("ok: hook-config change raised recorder-config-changed; attestation is digest/booleans only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
