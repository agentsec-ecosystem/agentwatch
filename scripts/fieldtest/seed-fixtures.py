#!/usr/bin/env python3
"""Seed field-test fixtures into the recorder store (M23).

Runs inside the recorder container. Creates deterministic sessions that the CLI
cases (CUJ-08/09/13/14, cost, union, demo) read:

  * ``ft-seed-main``   — hook records incl. an error, a denial, an approval, and a
                         ``secret-detected`` security event (fingerprinted at runtime)
  * ``ft-seed-sdk``    — an SDK-produced span (for the read-time union)
  * ``ft-seed-mcp-a/b`` — two sessions with different MCP tool surfaces (drift)

Also writes a minimal transcript + a git repo under ``--out`` when asked.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, "/work/packages/python-sdk/src")

from agentwatch.records import (  # noqa: E402
    AgentIdentity,
    AgentRecord,
    Approval,
    Outcome,
    Producer,
    ProducerKind,
    RecordPrivacyMode,
    SecurityEvent,
    SecurityEventType,
    StepType,
    ToolCall,
)
from agentwatch.store import RecordStore  # noqa: E402

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _at(minutes: int) -> datetime:
    return START + timedelta(minutes=minutes)


def _hook(session: str, tool: str, *, minute: int, outcome: Outcome = Outcome.OK,
          arguments: dict | None = None, span: str | None = None,
          approval: Approval | None = None, event: SecurityEvent | None = None,
          server: str | None = None, step: StepType = StepType.ACT) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="claude-code", name="claude-code"),
        tool=ToolCall(name=tool, server=server, arguments=arguments, privacy_mode=RecordPrivacyMode.METADATA_ONLY),
        outcome=outcome,
        started_at=_at(minute),
        producer=Producer(kind=ProducerKind.HOOK, name="claude-code"),
        span_id=span,
        approval=approval,
        step_type=step,
        security_event=event,
    )


def seed(store: RecordStore) -> None:
    secret_event = SecurityEvent(
        type=SecurityEventType.SECRET_DETECTED,
        emitted_at=_at(2),
        emitter="agentwatch",
        tool="Bash",
        evidence={"kinds": ["api-key"], "fingerprints": ["ft00fingerprint01"]},
    )
    records = [
        _hook("ft-seed-main", "Read", minute=0, arguments={"path": "app.py"}, span="m1", step=StepType.OBSERVE),
        _hook("ft-seed-main", "Bash", minute=1, arguments={"command": "pytest -q"}, span="m2"),
        _hook("ft-seed-main", "Bash", minute=2, outcome=Outcome.ERROR, arguments={"command": "make build"}, span="m3", event=secret_event),
        _hook("ft-seed-main", "Bash", minute=3, outcome=Outcome.DENIED, arguments={"command": "rm -rf /"}, span="m4", approval=Approval.DENIED),
        _hook("ft-seed-main", "Edit", minute=4, arguments={"path": "billing/charge.py"}, span="m5", approval=Approval.USER),
        _hook("ft-seed-sdk", "run", minute=10, span="s1"),
        _hook("ft-seed-mcp-a", "search", minute=20, server="payments", span="a1"),
        _hook("ft-seed-mcp-b", "charge", minute=30, server="payments", span="b1"),
    ]
    records[5] = AgentRecord(
        session_id="ft-seed-sdk",
        agent=AgentIdentity(identity="agentwatch", name="agentwatch"),
        tool=ToolCall(name="run"),
        outcome=Outcome.OK,
        started_at=_at(10),
        producer=Producer(kind=ProducerKind.SDK, name="agentwatch"),
        span_id="s1",
        step_type=StepType.ACT,
    )
    for record in records:
        store.append(record)


def _write_extras(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "transcript.jsonl").write_text(
        "\n".join(
            [
                '{"type":"tool_use","name":"Read","id":"m1"}',
                '{"type":"tool_use","name":"Bash","id":"m2"}',
                '{"type":"tool_use","name":"Bash","id":"m3"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    repo = out / "gitrepo"
    repo.mkdir(exist_ok=True)
    try:
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "file.txt").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "file.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-q", "-m", "init"],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", default="/data/agentwatch/records.jsonl")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    seed(RecordStore(args.store))
    if args.out:
        _write_extras(Path(args.out))
    print(f"seed-fixtures: seeded {args.store}")
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
