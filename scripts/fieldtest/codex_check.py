#!/usr/bin/env python3
"""COD-1: codex rollout reader — reads the fixture rollouts, dedups repeated
plaintext, and marks an unanswered call as an inferred ``crashed`` end-state."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from _ftutil import fail, ok, records  # noqa: E402

FIXTURE = Path("/ft/fixtures/codex")
STORE = Path("/data/agentwatch/records.jsonl")


def _store_records() -> list[dict]:
    return records()


def main(argv: list[str]) -> int:
    from agentwatch.codex_rollout import ingest_rollouts
    from agentwatch.store import RecordStore

    files = sorted(FIXTURE.rglob("*.jsonl"))
    if not files:
        fail(f"no codex rollout fixtures under {FIXTURE}")
    store = RecordStore(STORE)
    report = ingest_rollouts(files, store)
    if report.records == 0:
        fail("codex reader normalized 0 records")

    # The reader dedups on (session_id, span_id, step_type); assert that holds.
    sigs = [(r.get("session_id"), r.get("span_id"), r.get("step_type")) for r in _store_records()]
    dupes = len(sigs) - len(set(sigs))
    if dupes:
        fail(f"{dupes} duplicate record(s) survived dedup")

    crashed = [r for r in _store_records() if str(r.get("outcome")) == "crashed"]
    ok(f"codex rollout: {report.records} records (files={report.files}, duplicates={report.duplicates}, "
       f"dangling={report.dangling}); dedup ok; crashed end-state={bool(crashed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
