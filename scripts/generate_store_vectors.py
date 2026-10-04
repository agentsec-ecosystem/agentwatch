#!/usr/bin/env python3
"""Generate the committed store conformance vectors (PRD 38 §Q6, issue #223).

Vectors are built with the real ``RecordStore`` writer, so the envelope format is
canonical. Verdicts are *authored* from the documented rules here and the
generator asserts the shipped ``store.py`` agrees before writing the table — the
standalone verifier (``schema/vectors/verify_store.py``) is independently checked
against the same table in CI.

Usage: python scripts/generate_store_vectors.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "schema" / "vectors" / "store"

sys.path.insert(0, str(REPO / "packages" / "python-sdk" / "src"))

from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall  # noqa: E402
from agentwatch.store import RecordStore  # noqa: E402

_OLD = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(name: str, session: str = "sess-1", when: datetime = _OLD) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=name),
        outcome=Outcome.OK,
        started_at=when,
    )


def _build_valid(path: Path) -> None:
    store = RecordStore(path, durability="none")
    store.append(_record("A", "sess-1"))
    store.append(_record("B", "sess-2"))
    store.append(_record("C", "sess-1"))


# id -> (builder, authored verdict). "line" is only meaningful for parse errors.
CASES: dict[str, dict[str, object]] = {
    "valid": {"ok": True, "broken_at": None, "line": None},
    "tampered": {"ok": False, "broken_at": 1, "line": None},
    "tombstoned": {"ok": True, "broken_at": None, "line": None},
    "purged": {"ok": True, "broken_at": None, "line": None},
    "gap": {"ok": False, "broken_at": 2, "line": None},
    "checkpoint": {"ok": True, "broken_at": None, "line": None},
    "unsupported-format": {"ok": False, "broken_at": None, "line": 1},
}


def _tamper(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    envelope = json.loads(lines[2])  # seq 1 (line 0 is the format marker)
    assert envelope["seq"] == 1
    envelope["record"]["tool"]["name"] = "Tampered"
    lines[2] = json.dumps(envelope, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _gap(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[2]  # drop the seq-1 entry; the next entry no longer chains
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="agentwatch-vectors-"))

    # Build the source stores with the real writer.
    valid = tmp / "valid.jsonl"
    _build_valid(valid)

    tampered = tmp / "tampered.jsonl"
    shutil.copyfile(valid, tampered)
    _tamper(tampered)

    gap = tmp / "gap.jsonl"
    shutil.copyfile(valid, gap)
    _gap(gap)

    tombstoned = tmp / "tombstoned.jsonl"
    _build_valid(tombstoned)
    RecordStore(tombstoned, durability="none").apply_retention(
        retention_days=1, now=datetime(2026, 3, 1, tzinfo=timezone.utc)
    )

    purged = tmp / "purged.jsonl"
    _build_valid(purged)
    RecordStore(purged, durability="none").purge_session("sess-2")

    checkpoint = tmp / "checkpoint.jsonl"
    _build_valid(checkpoint)
    RecordStore(checkpoint, durability="none").checkpoint()

    unsupported = tmp / "unsupported-format.jsonl"
    unsupported.write_text(json.dumps({"format": 99}) + "\n", encoding="utf-8")

    # Assert the shipped verifier agrees with the authored verdicts, then copy.
    vectors: list[dict[str, object]] = []
    for case_id, expected in CASES.items():
        source = tmp / f"{case_id}.jsonl"
        status = RecordStore(source, durability="none").verify()
        if (
            status.ok != expected["ok"]
            or status.broken_at != expected["broken_at"]
            or status.line != expected["line"]
        ):
            print(
                f"!! {case_id}: store.py gave ok={status.ok} broken_at={status.broken_at} "
                f"line={status.line}; expected {expected}",
                file=sys.stderr,
            )
            return 1
        shutil.copyfile(source, OUT / source.name)
        vectors.append({"id": case_id, "file": source.name, **expected})

    table = {
        "schema": "agentwatch.store-vectors/0.1.0",
        "description": "Store/chain conformance vectors; see schema/vectors/README.md.",
        "vectors": vectors,
    }
    (OUT / "expected-verdicts.json").write_text(
        json.dumps(table, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(vectors)} vectors to {OUT.relative_to(REPO)}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
