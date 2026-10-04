#!/usr/bin/env python3
"""agentwatch-verify — standalone, dependency-free verifier (M15 S12, #232).

A bundle only verifiable by installing the tool that produced it is weak evidence.
This zipapp verifies an agentwatch evidence bundle (M15 S1) or a store/chain file
with **no Python environment, no daemon, and no network**, importing nothing from
``agentwatch``.

Usage:
    agentwatch-verify <bundle.zip>
    agentwatch-verify <store.jsonl>
    agentwatch-verify --table          # run the published store vectors (Q6)
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

BUNDLE_FORMAT = "agentwatch-evidence/1"
GENESIS = "0" * 64  # GENESIS_PREV_HASH (store-format spec)
SUPPORTED_STORE_FORMAT = 1


def _canonical(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _entry_hash(prev: str, payload: object) -> str:
    return hashlib.sha256((prev + _canonical(payload)).encode("utf-8")).hexdigest()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_store(path: Path) -> dict[str, object]:
    """Recompute a store/chain file and report ok/broken_at/line."""
    if not path.exists():
        return {"ok": True, "broken_at": None, "line": None}
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
                if int(envelope["format"]) != SUPPORTED_STORE_FORMAT:
                    supported = False
                continue
            if "seq" not in envelope:
                raise ValueError("not an envelope")
            entries.append(envelope)
        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
            parse_errors.append(int(entries[-1].get("seq", -1)) + 1 if entries else 0)
            parse_lines.append(line_number)
    if not supported:
        return {"ok": False, "broken_at": None, "line": 1}
    if parse_errors:
        return {"ok": False, "broken_at": parse_errors[0], "line": parse_lines[0]}
    prev = GENESIS
    for expected_seq, envelope in enumerate(entries):
        seq = int(envelope["seq"])
        if seq != expected_seq or str(envelope.get("prev_hash", "")) != prev:
            return {"ok": False, "broken_at": seq, "line": None}
        if envelope.get("checkpoint"):
            payload = {
                "checkpoint": True,
                "entries": int(envelope.get("entries", 0)),
                "at": str(envelope.get("at", "")),
            }
            if _entry_hash(prev, payload) != str(envelope["hash"]):
                return {"ok": False, "broken_at": seq, "line": None}
        elif not envelope.get("tombstone", False) and envelope.get("record") is not None:
            if _entry_hash(prev, envelope["record"]) != str(envelope["hash"]):
                return {"ok": False, "broken_at": seq, "line": None}
        prev = str(envelope["hash"])
    return {"ok": True, "broken_at": None, "line": None}


def _verify_segment(data: bytes, problems: list[str]) -> bool:
    for line in data.decode("utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or "record" not in row:
            problems.append("malformed records.ndjson row")
            return False
        if _entry_hash(str(row.get("prev_hash", "")), row["record"]) != str(row.get("hash")):
            problems.append("chain segment failed verification")
            return False
    return True


def verify_bundle(path: Path) -> dict[str, object]:
    """Verify a bundle offline: member hashes, then the chain segment."""
    problems: list[str] = []
    bundle_format = ""
    intact = complete = leak_free = False
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names:
                return {"ok": False, "bundle_format": "", "problems": ["manifest.json missing"]}
            manifest = json.loads(archive.read("manifest.json"))
            bundle_format = str(manifest.get("bundle_format", ""))
            if bundle_format != BUNDLE_FORMAT:
                return {
                    "ok": False,
                    "bundle_format": bundle_format,
                    "intact": False,
                    "complete": False,
                    "leak_free": False,
                    "problems": [f"unknown bundle format version {bundle_format!r}"],
                }
            for name, digest in manifest.get("members", {}).items():
                if name not in names:
                    problems.append(f"member missing: {name}")
                    continue
                if _sha256(archive.read(name)) != digest:
                    problems.append(f"member tampered: {name}")
            intact = _verify_segment(archive.read("records.ndjson"), problems) and not any(
                "tampered" in p or "missing" in p for p in problems
            )
            complete = bool(json.loads(archive.read("coverage.json")).get("complete", False))
            leak_free = bool(json.loads(archive.read("privacy.json")).get("leak_free", False))
    except (zipfile.BadZipFile, OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        return {
            "ok": False,
            "bundle_format": bundle_format,
            "problems": [f"unreadable bundle: {exc}"],
        }
    return {
        "ok": intact and not problems,
        "bundle_format": bundle_format,
        "intact": intact,
        "complete": complete,
        "leak_free": leak_free,
        "problems": problems,
    }


def _check_table(base: Path | None = None) -> int:
    here = Path(__file__).resolve().parent
    root = base or (here / "store")
    if not (root / "expected-verdicts.json").is_file():
        root = Path.cwd() / "schema" / "vectors" / "store"
    table = json.loads((root / "expected-verdicts.json").read_text(encoding="utf-8"))
    failures = 0
    for vector in table["vectors"]:
        verdict = verify_store(root / vector["file"])
        expected = (vector["ok"], vector["broken_at"], vector["line"])
        actual = (verdict["ok"], verdict["broken_at"], verdict["line"])
        status = "ok " if actual == expected else "FAIL"
        print(f"[{status}] {vector['id']:20} expected={expected} actual={actual}")
        failures += 0 if actual == expected else 1
    print(f"standalone verifier matched {len(table['vectors']) - failures}/{len(table['vectors'])}")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: agentwatch-verify <bundle.zip|store.jsonl> | --table [DIR]", file=sys.stderr)
        return 2
    if argv[0] == "--table":
        base = Path(argv[1]) if len(argv) > 1 else None
        return _check_table(base)
    target = Path(argv[0])
    if target.suffix == ".zip":
        report = verify_bundle(target)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["ok"] else 1
    verdict = verify_store(target)
    print(json.dumps(verdict, sort_keys=True))
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
