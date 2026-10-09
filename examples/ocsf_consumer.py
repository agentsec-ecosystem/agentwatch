#!/usr/bin/env python3
"""Reference OCSF 1.5.0 stream consumer for agentwatch (M27 SIEM-1, #346).

The **SIEM flavor** of the reference consumer: agentwatch emits security events
as OCSF 1.5.0 objects (`agentwatch export-session <id> --format ocsf`); a SOC
consumer reads that NDJSON and validates the OCSF envelope before ingesting it.
A small, complete example — copy it, adapt it, ship it.

It is a *consumer*: events-only, bounded (one JSON object per line), and it never
touches the local record store.

Run it from a checkout::

    agentwatch export-session <id> --format ocsf | python examples/ocsf_consumer.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

try:
    from agentwatch.ocsf import OCSF_VERSION
except ImportError:  # pragma: no cover - guidance when run without the SDK
    print(
        "ocsf_consumer: install the agentwatch SDK first (pip install -e packages/python-sdk)",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

_REQUIRED_INT_FIELDS = ("class_uid", "category_uid", "activity_id", "time")


def parse_objects(text: str) -> Iterator[dict[str, Any]]:
    """Yield each JSON object in an OCSF NDJSON stream, skipping blank lines."""
    for line in text.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            yield item


def validate_objects(objects: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate each OCSF object; return the valid ones and the problems.

    A problem is a wrong/missing ``metadata.version`` or a missing required
    integer field — never a crash, so a malformed line is visible, not fatal.
    """
    valid: list[dict[str, Any]] = []
    problems: list[str] = []
    for index, obj in enumerate(objects):
        metadata = obj.get("metadata")
        version = metadata.get("version") if isinstance(metadata, dict) else None
        if version != OCSF_VERSION:
            problems.append(f"object {index}: version {version!r} != {OCSF_VERSION!r}")
            continue
        missing = [field for field in _REQUIRED_INT_FIELDS if not isinstance(obj.get(field), int)]
        if missing:
            problems.append(f"object {index}: missing/invalid {', '.join(missing)}")
            continue
        valid.append(obj)
    return valid, problems


def read_input(path: str | None) -> str:
    """Read a file, or stdin when no path is given."""
    if path is None or path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reference OCSF 1.5.0 consumer")
    parser.add_argument("--input", default=None, help="OCSF NDJSON file (default: stdin)")
    parser.add_argument("--json", action="store_true", help="emit validated objects as JSON")
    args = parser.parse_args(argv)

    valid, problems = validate_objects(parse_objects(read_input(args.input)))
    if args.json:
        for obj in valid:
            print(json.dumps(obj, sort_keys=True))
    else:
        for obj in valid:
            print(f"{obj['class_name']}  {obj['activity_name']}")
    for problem in problems:
        print(f"ocsf_consumer: rejected {problem}", file=sys.stderr)
    print(f"ocsf_consumer: {len(valid)} valid, {len(problems)} rejected")
    return 0 if not problems else 1


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
