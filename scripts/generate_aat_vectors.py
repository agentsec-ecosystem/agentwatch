#!/usr/bin/env python3
"""Generate the committed AAT conformance vectors (M26 AAT-4, issue #314).

Vectors are built with the real ``export_aat`` writer, so the bundle shape is
canonical. Verdicts are *authored* from the published rules here and the
generator asserts the shipped ``agentwatch.aat.verify_aat_report`` agrees before
writing the table — the standalone verifier (``schema/vectors/verify_aat.py``)
is independently checked against the same table in CI.

Usage: python scripts/generate_aat_vectors.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "schema" / "vectors" / "aat"

sys.path.insert(0, str(REPO / "packages" / "python-sdk" / "src"))

from agentwatch.aat import export_aat, verify_aat_report  # noqa: E402
from agentwatch.records import (  # noqa: E402
    AgentIdentity,
    AgentRecord,
    Outcome,
    ToolCall,
)
from agentwatch.session_export import export_session  # noqa: E402
from agentwatch.store import RecordStore  # noqa: E402

_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

# id -> authored verdict. failed_entries: [] = valid, [-1] = bundle-level failure.
CASES: dict[str, dict[str, object]] = {
    "valid": {"ok": True, "failed_entries": []},
    "tampered": {"ok": False, "failed_entries": [1]},
    "unmapped": {"ok": True, "failed_entries": []},
    "unsupported-revision": {"ok": False, "failed_entries": [-1]},
}


def _record(name: str, span: str, *, identity: str = "agent-1") -> AgentRecord:
    return AgentRecord(
        session_id="sess-1",
        agent=AgentIdentity(identity=identity),
        tool=ToolCall(name=name),
        outcome=Outcome.OK,
        started_at=_AT,
        span_id=span,
    )


def _bundle(workdir: Path, records: list[AgentRecord]) -> dict[str, Any]:
    store = RecordStore(workdir / "source.jsonl", durability="none")
    for record in records:
        store.append(record)
    return export_aat(export_session(store, "sess-1"), privacy_mode="metadata-only")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="agentwatch-aat-vectors-"))

    valid = _bundle(
        workdir,
        [_record("A", "sp-1"), _record("B", "sp-2"), _record("C", "sp-3")],
    )

    tampered = json.loads(json.dumps(valid))
    tampered["records"][1]["agentwatch"]["tool"]["name"] = "Tampered"

    # A bundle whose records leave AAT fields unmapped: surfaced, never invented,
    # and still a valid chain (unmapped is not a verification failure).
    unmapped = json.loads(json.dumps(valid))
    for entry in unmapped["records"]:
        assert entry.get("unmapped"), "unmapped fields must be surfaced"

    unsupported = json.loads(json.dumps(valid))
    unsupported["aat_version"] = "draft-sharif-agent-audit-trail-99"

    built: dict[str, dict[str, Any]] = {
        "valid": valid,
        "tampered": tampered,
        "unmapped": unmapped,
        "unsupported-revision": unsupported,
    }

    vectors: list[dict[str, object]] = []
    for case_id, expected in CASES.items():
        report = verify_aat_report(built[case_id])
        actual = (report.ok, [problem.index for problem in report.problems])
        want = (expected["ok"], list(expected["failed_entries"]))  # type: ignore[arg-type]
        if actual != want:
            print(
                f"!! {case_id}: verify_aat_report gave {actual}; expected {want}",
                file=sys.stderr,
            )
            shutil.rmtree(workdir, ignore_errors=True)
            return 1
        path = OUT / f"{case_id}.json"
        path.write_text(
            json.dumps(built[case_id], indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        vectors.append({"id": case_id, "file": path.name, **expected})

    table = {
        "schema": "agentwatch.aat-vectors/0.1.0",
        "description": "AAT bundle conformance vectors; see schema/vectors/README.md.",
        "vectors": vectors,
    }
    (OUT / "expected-verdicts.json").write_text(
        json.dumps(table, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(vectors)} vectors to {OUT.relative_to(REPO)}")
    shutil.rmtree(workdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
