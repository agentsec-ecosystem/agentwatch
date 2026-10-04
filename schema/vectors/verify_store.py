#!/usr/bin/env python3
"""Standalone, dependency-free store/chain verifier (PRD 38 §Q6, issue #223).

A second, independent implementation of the documented store verification rules.
It imports nothing from ``agentwatch``: it reads the JSONL envelopes, recomputes
the sha256 chain from the published rules, and reports the same verdict
(``ok`` / ``broken_at`` / ``line``) as ``agentwatch.store.RecordStore.verify``.

Both implementations are checked against ``expected-verdicts.json`` so a rule
that drifts in either one is surfaced as a contract bug. This is the reference
implementation that the M15 S12 standalone verifier will formalize.

Usage:
    python schema/vectors/verify_store.py [store.jsonl]
    python schema/vectors/verify_store.py --table   # check every vector
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
GENESIS = "0" * 64  # GENESIS_PREV_HASH (store-format spec)
SUPPORTED_FORMAT = 1


@dataclass(frozen=True)
class Verdict:
    ok: bool
    broken_at: int | None
    line: int | None = None


def _canonical(record: object) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _entry_hash(prev_hash: str, payload: object) -> str:
    return hashlib.sha256((prev_hash + _canonical(payload)).encode("utf-8")).hexdigest()


def verify(path: Path) -> Verdict:
    """Recompute the chain and return the verdict, mirroring the store rules."""
    if not path.exists():
        return Verdict(ok=True, broken_at=None)

    supported = True
    parse_errors: list[int] = []
    parse_lines: list[int] = []
    entries: list[dict[str, object]] = []

    for line_number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
        if not line:
            continue
        try:
            envelope = json.loads(line)
            if not isinstance(envelope, dict):
                raise ValueError("not an envelope")
            if "format" in envelope and "seq" not in envelope:
                if int(envelope["format"]) != SUPPORTED_FORMAT:
                    supported = False
                continue
            if "seq" not in envelope:
                raise ValueError("not an envelope")
            entries.append(envelope)
        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
            parse_errors.append(entries[-1].get("seq", -1) + 1 if entries else 0)
            parse_lines.append(line_number)

    if not supported:
        return Verdict(ok=False, broken_at=None, line=1)
    if parse_errors:
        return Verdict(ok=False, broken_at=parse_errors[0], line=parse_lines[0])

    prev = GENESIS
    for expected_seq, envelope in enumerate(entries):
        seq = int(envelope["seq"])
        if seq != expected_seq or str(envelope.get("prev_hash", "")) != prev:
            return Verdict(ok=False, broken_at=seq)
        if envelope.get("checkpoint"):
            payload = {
                "checkpoint": True,
                "entries": int(envelope.get("entries", 0)),
                "at": str(envelope.get("at", "")),
            }
            if _entry_hash(prev, payload) != str(envelope["hash"]):
                return Verdict(ok=False, broken_at=seq)
        elif not envelope.get("tombstone", False) and envelope.get("record") is not None:
            if _entry_hash(prev, envelope["record"]) != str(envelope["hash"]):
                return Verdict(ok=False, broken_at=seq)
        prev = str(envelope["hash"])

    return Verdict(ok=True, broken_at=None)


def _check_table() -> int:
    table = json.loads((HERE / "store" / "expected-verdicts.json").read_text(encoding="utf-8"))
    failures = 0
    for vector in table["vectors"]:
        path = HERE / "store" / vector["file"]
        verdict = verify(path)
        expected = (vector["ok"], vector["broken_at"], vector["line"])
        actual = (verdict.ok, verdict.broken_at, verdict.line)
        status = "ok " if actual == expected else "FAIL"
        print(f"[{status}] {vector['id']:20} expected={expected} actual={actual}")
        if actual != expected:
            failures += 1
    if failures:
        print(f"{failures} vector(s) diverged from the expected verdict table", file=sys.stderr)
        return 1
    print(f"standalone verifier matches all {len(table['vectors'])} verdicts")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "--table":
        return _check_table()
    verdict = verify(Path(argv[0]))
    print(json.dumps({"ok": verdict.ok, "broken_at": verdict.broken_at, "line": verdict.line}))
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
