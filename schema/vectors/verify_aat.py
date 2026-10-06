#!/usr/bin/env python3
"""Standalone, dependency-free AAT bundle verifier (M26 AAT-4, issue #314).

A second, independent implementation of the published IETF Agent Audit Trail
chain rules. It imports nothing from ``agentwatch``: it reads the JSON bundle,
recomputes each entry's sha256 chain hash and its inter-entry linkage, and
reports the same verdict as ``agentwatch.aat.verify_aat_report``.

Both implementations are checked against ``aat/expected-verdicts.json`` so a
rule that drifts in either one is surfaced as a contract bug.

Usage:
    python schema/vectors/verify_aat.py <bundle.json>
    python schema/vectors/verify_aat.py --table   # check every vector
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
AAT_DRAFT = "draft-sharif-agent-audit-trail-06"


@dataclass(frozen=True)
class Verdict:
    """The verdict for a bundle: ``ok`` plus the indices that failed (-1 = bundle)."""

    ok: bool
    failed: tuple[int, ...]


def _canonical(record: object) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _entry_hash(prev_hash: str, record: object) -> str:
    return hashlib.sha256((prev_hash + _canonical(record)).encode("utf-8")).hexdigest()


def _entry_error(entry: object, prev_hash: str | None) -> str | None:
    """Why an entry is untrusted, or ``None`` when it verifies."""
    if not isinstance(entry, dict):
        return "entry is not an object"
    native = entry.get("agentwatch")
    chain = entry.get("chain")
    if not isinstance(native, dict) or not isinstance(chain, dict):
        return "missing agentwatch record or chain envelope"
    declared_prev = chain.get("prev_hash")
    declared_hash = chain.get("hash")
    if not isinstance(declared_prev, str) or not isinstance(declared_hash, str):
        return "chain envelope has no prev_hash/hash"
    if prev_hash is not None and declared_prev != prev_hash:
        return "chain linkage broken"
    if _entry_hash(declared_prev, native) != declared_hash:
        return "chain hash mismatch"
    return None


def verify(path: Path) -> Verdict:
    """Recompute the AAT chain and return the verdict, mirroring the AAT rules."""
    try:
        bundle = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Verdict(ok=False, failed=(-1,))
    if not isinstance(bundle, dict) or bundle.get("aat_version") != AAT_DRAFT:
        return Verdict(ok=False, failed=(-1,))
    entries = bundle.get("records")
    if not isinstance(entries, list):
        return Verdict(ok=False, failed=(-1,))

    failed: list[int] = []
    prev_hash: str | None = None
    for index, entry in enumerate(entries):
        if _entry_error(entry, prev_hash) is not None:
            failed.append(index)
        chain = entry.get("chain") if isinstance(entry, dict) else None
        declared = chain.get("hash") if isinstance(chain, dict) else None
        if isinstance(declared, str):
            prev_hash = declared
    return Verdict(ok=not failed, failed=tuple(failed))


def _check_table() -> int:
    table = json.loads((HERE / "aat" / "expected-verdicts.json").read_text(encoding="utf-8"))
    failures = 0
    for vector in table["vectors"]:
        path = HERE / "aat" / vector["file"]
        verdict = verify(path)
        expected = (vector["ok"], tuple(vector["failed_entries"]))
        actual = (verdict.ok, tuple(verdict.failed))
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
    print(json.dumps({"ok": verdict.ok, "failed": list(verdict.failed)}))
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
