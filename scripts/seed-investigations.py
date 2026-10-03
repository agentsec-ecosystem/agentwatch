#!/usr/bin/env python3
"""Seed the investigation-cookbook dataset into a local store (M8 addition J3).

Builds three reproducible sessions — a retry loop, a caught secret, and a denied
call — used by ``docs/examples/investigations/*.md``. Contains **no real secrets**
(the secret payload is already redacted and only the security event is recorded),
so ``agentwatch verify-privacy`` passes on the seeded store.

Usage::

    python3 scripts/seed-investigations.py --store /tmp/agentwatch-demo
    agentwatch --set store.path=/tmp/agentwatch-demo view
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "packages/python-sdk/src"))

from agentwatch.records import (  # noqa: E402
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    SecurityEvent,
    SecurityEventType,
    StepType,
    ToolCall,
)
from agentwatch.store import RecordStore  # noqa: E402

_T0 = datetime(2026, 3, 1, 14, 0, tzinfo=timezone.utc)


def _record(
    session: str,
    name: str,
    offset: int,
    *,
    outcome: Outcome = Outcome.OK,
    arguments: dict[str, object] | None = None,
    security_event: SecurityEvent | None = None,
    step_type: StepType | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="demo-agent", name="demo-agent"),
        tool=ToolCall(
            name=name,
            arguments=arguments,
            privacy_mode=RecordPrivacyMode.TRUNCATED if arguments else None,
        ),
        outcome=outcome,
        started_at=_T0 + timedelta(seconds=offset),
        security_event=security_event,
        step_type=step_type,
    )


def build_records() -> list[AgentRecord]:
    """The cookbook dataset: loop, secret, and denied scenarios."""
    return [
        # Loop found: the agent re-reads the same file over and over.
        _record("sess-loop", "Read", 0, arguments={"path": "src/app.py"}),
        _record("sess-loop", "Read", 1, arguments={"path": "src/app.py"}),
        _record("sess-loop", "Read", 2, arguments={"path": "src/app.py"}),
        _record("sess-loop", "Read", 3, arguments={"path": "src/app.py"}),
        # Secret caught: payload is redacted; the security event is what matters.
        _record(
            "sess-secret",
            "Bash",
            0,
            arguments={"command": "export KEY=<REDACTED:api-key>"},
            security_event=SecurityEvent(
                type=SecurityEventType.SECRET_DETECTED,
                emitted_at=_T0,
                emitter="claude-code",
                tool="Bash",
                reason="api-key in tool arguments",
            ),
            step_type=StepType.ACT,
        ),
        # Denied call reviewed: harness refused a dangerous command.
        _record(
            "sess-denied",
            "Bash",
            0,
            outcome=Outcome.DENIED,
            security_event=SecurityEvent(
                type=SecurityEventType.DENIED,
                emitted_at=_T0,
                emitter="claude-code",
                tool="Bash",
                reason="policy: destructive command refused",
            ),
            step_type=StepType.OBSERVE,
        ),
    ]


def seed(store_dir: Path) -> int:
    store = RecordStore(store_dir.expanduser() / "records.jsonl")
    records = build_records()
    for record in records:
        store.append(record)
    print(f"seeded {len(records)} records into {store.path}")
    return len(records)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store",
        type=Path,
        default=Path.home() / ".agentwatch",
        help="store directory (default: ~/.agentwatch)",
    )
    args = parser.parse_args(argv)
    seed(args.store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
