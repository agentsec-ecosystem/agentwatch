#!/usr/bin/env python3
"""Reference re-implementation of the evidence-bundle verifier (M15 S12, #232).

Published in ``docs/reference/evidence-verifier.md`` so an auditor can read the
~100 lines and re-implement the check in any language. Stdlib only; imports
nothing from ``agentwatch``. It consumes the M15 S1 bundle format and the M15 J1
store format.

Run:
    python scripts/agentwatch_verify/reference.py bundle.zip
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

EXPECTED_BUNDLE_FORMAT = "agentwatch-evidence/1"
ZERO_HASH = "0" * 64


def _digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _link_hash(parent: str, body: object) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(parent.encode() + canonical.encode()).hexdigest()


def _segment_ok(blob: bytes) -> bool:
    for raw in blob.splitlines():
        if not raw.strip():
            continue
        row = json.loads(raw)
        if not isinstance(row, dict) or "record" not in row or "prev_hash" not in row:
            return False
        if _link_hash(str(row["prev_hash"]), row["record"]) != row["hash"]:
            return False
    return True


def verify_bundle(path: Path) -> dict[str, object]:
    """Return a verdict dict; never collapses the three independent verdicts."""
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as error:
        return {"ok": False, "problems": [f"unreadable zip: {error}"]}
    with archive:
        names = archive.namelist()
        if "manifest.json" not in names:
            return {"ok": False, "problems": ["no manifest.json"]}
        manifest = json.loads(archive.read("manifest.json").decode())
        version = manifest.get("bundle_format", "")
        if version != EXPECTED_BUNDLE_FORMAT:
            return {"ok": False, "problems": [f"unsupported bundle format {version}"]}

        problems: list[str] = []
        for member, expected in manifest.get("members", {}).items():
            if member not in names:
                problems.append(f"missing member {member}")
            elif _digest(archive.read(member)) != expected:
                problems.append(f"hash mismatch for {member}")

        intact = _segment_ok(archive.read("records.ndjson")) and not problems
        complete = json.loads(archive.read("coverage.json"))["complete"]
        leak_free = json.loads(archive.read("privacy.json"))["leak_free"]
    return {
        "ok": intact and complete and leak_free,
        "bundle_format": version,
        "intact": intact,
        "complete": complete,
        "leak_free": leak_free,
        "problems": problems,
    }


def verify_store(path: Path) -> dict[str, object]:
    """Verify a store/chain JSONL file against the published rules."""
    parent = ZERO_HASH
    index = 0
    format_ok = True
    bad_line: int | None = None
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line:
            continue
        try:
            envelope = json.loads(line)
            if not isinstance(envelope, dict):
                raise ValueError("not an object")
        except (json.JSONDecodeError, ValueError):
            bad_line = number
            break
        if "seq" not in envelope:
            if int(envelope.get("format", 1)) != 1:
                format_ok = False
            continue
        body: object = envelope.get("record")
        if envelope.get("checkpoint"):
            body = {
                "checkpoint": True,
                "entries": envelope.get("entries", 0),
                "at": envelope.get("at", ""),
            }
        if body is not None and not envelope.get("tombstone"):
            if envelope["seq"] != index or envelope["prev_hash"] != parent:
                return {"ok": False, "broken_at": envelope["seq"], "line": None}
            if _link_hash(parent, body) != envelope["hash"]:
                return {"ok": False, "broken_at": envelope["seq"], "line": None}
        parent = envelope["hash"]
        index += 1
    if not format_ok:
        return {"ok": False, "broken_at": None, "line": 1}
    if bad_line is not None:
        return {"ok": False, "broken_at": index, "line": bad_line}
    return {"ok": True, "broken_at": None, "line": None}


def main(argv: list[str]) -> int:
    report = verify_bundle(Path(argv[0])) if argv else {"ok": False, "problems": ["no path"]}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
