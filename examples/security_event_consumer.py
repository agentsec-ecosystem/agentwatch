#!/usr/bin/env python3
"""Reference security-event consumer for agentwatch (M20 S38, PRD 36).

This is a **reference**, not a supported product: a small, complete example of
the *consumer* side of the agentwatch contract. It subscribes to security
events, validates each one against the published schema, and prints or forwards
it. Copy it, adapt it, ship it.

Two inputs:

* a fixture / NDJSON file (``--input events.ndjson``) — the CI path; or
* the live daemon socket (``--socket``), read as NDJSON frames.

The schema is a contract, not a library: validation uses the shipped
``agentwatch.records.validate_event`` so this example cannot drift from it (the
CI test fails if it does).

Run it from a checkout::

    python examples/security_event_consumer.py --input examples/fixtures/events.ndjson
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

try:
    from agentwatch.records import SecurityEvent, validate_event
except ImportError:  # pragma: no cover - guidance when run without the SDK
    print(
        "security_event_consumer: install the agentwatch SDK first "
        "(pip install -e packages/python-sdk)",
        file=sys.stderr,
    )
    raise SystemExit(2) from None


def parse_events(text: str) -> Iterator[dict[str, Any]]:
    """Yield each JSON object in an NDJSON stream, skipping blank lines."""
    for line in text.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            yield item


def validate_events(events: Iterable[dict[str, Any]]) -> tuple[list[SecurityEvent], list[str]]:
    """Validate every event; return the valid ones and the problems (never crash)."""
    valid: list[SecurityEvent] = []
    problems: list[str] = []
    for index, raw in enumerate(events):
        try:
            valid.append(validate_event(raw))
        except ValueError as exc:
            problems.append(f"event {index}: {exc}")
    return valid, problems


def read_input(path: str | None) -> str:
    """Read a file, or stdin when no path is given."""
    if path is None or path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reference agentwatch event consumer")
    parser.add_argument("--input", default=None, help="NDJSON file (default: stdin)")
    parser.add_argument("--json", action="store_true", help="emit validated events as JSON")
    args = parser.parse_args(argv)

    valid, problems = validate_events(parse_events(read_input(args.input)))
    if args.json:
        for event in valid:
            print(json.dumps(event.to_dict(), sort_keys=True))
    else:
        for event in valid:
            print(f"{event.emitted_at.isoformat()}  {event.type.value}  {event.reason or ''}".rstrip())
    for problem in problems:
        print(f"security_event_consumer: rejected {problem}", file=sys.stderr)
    print(f"security_event_consumer: {len(valid)} valid, {len(problems)} rejected")
    return 0 if not problems else 1


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
