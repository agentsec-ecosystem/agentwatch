"""``agentwatch demo`` — prove the pipeline end to end (M19 S31, PRD 35).

``init`` installs hooks and ``doctor`` checks the environment, but neither
exercises the pipeline: adapter -> redaction -> store -> chain. This module
synthesizes a handful of hook messages and drives them through the **real**
adapter and store path (the same functions the daemon calls), then reports the
timeline, the chain verdict, and the redaction result.

Records are tagged ``producer.kind: demo`` (S26) so synthetic data can never be
mistaken for evidence, and are excluded from coverage and bundles. ``--purge``
tombstones the demo session, leaving the store exactly as found.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agentwatch.adapters import claude_code
from agentwatch.context_snapshot import environment_snapshot
from agentwatch.hook import default_socket_path
from agentwatch.records import AgentRecord, Producer, ProducerKind, SecurityEventType
from agentwatch.redact import RedactionConfig
from agentwatch.store import RecordStore

DEMO_SESSION_ID = "demo"
DEMO_PRODUCER = Producer(kind=ProducerKind.DEMO, name="agentwatch")


@dataclass(frozen=True)
class DemoResult:
    """The outcome of one demo run (all synthetic; never evidence)."""

    session_id: str
    records: tuple[AgentRecord, ...]
    chain_ok: bool
    chain_checked: int
    chain_broken_at: int | None
    redaction_kinds: tuple[str, ...]
    daemon_reachable: bool
    accepted: int = 0
    denied: int = 0
    errored: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "records": len(self.records),
            "chain": {
                "ok": self.chain_ok,
                "checked": self.chain_checked,
                "broken_at": self.chain_broken_at,
            },
            "redaction_kinds": list(self.redaction_kinds),
            "daemon_reachable": self.daemon_reachable,
            "timeline": [
                {
                    "tool": record.tool.name,
                    "outcome": record.outcome.value,
                    "approval": record.approval.value if record.approval else None,
                }
                for record in self.records
            ],
        }


def daemon_reachable(socket_path: str | None = None) -> bool:
    """Whether a daemon is listening on the socket right now (never raises)."""
    path = socket_path or default_socket_path()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.5)
        sock.connect(path)
        return True
    except OSError:
        return False
    finally:
        sock.close()


def build_messages(
    now: datetime | None = None,
    *,
    cwd: str | None = None,
    include_principal: bool = True,
) -> list[dict[str, Any]]:
    """The synthetic hook messages: a secret to redact, a denial, and an error."""
    moment = now or datetime.now(timezone.utc)
    # Built at runtime so no provider-shaped literal sits in the source.
    secret = "sk-" + "abcdefghijklmnop"
    base: dict[str, Any] = {"session_id": DEMO_SESSION_ID, "cwd": cwd or str(Path.cwd())}

    def at(seconds: int) -> str:
        return (moment + timedelta(seconds=seconds)).isoformat()

    return [
        {
            "phase": "session-start",
            "harness": "claude-code",
            "event": {
                **base,
                "reason": "startup",
                "timestamp": at(0),
                "environment": environment_snapshot(cwd, include_principal=include_principal),
            },
        },
        {
            "phase": "prompt",
            "harness": "claude-code",
            "event": {
                **base,
                "prompt": "Clean the build and show me the config.",
                "timestamp": at(1),
            },
        },
        {
            "phase": "pre",
            "harness": "claude-code",
            "event": {
                **base,
                "tool_name": "Bash",
                "tool_use_id": "demo-call-1",
                "tool_input": {"command": f"curl -H 'x-api-key: {secret}' https://example.invalid"},
                "timestamp": at(2),
            },
        },
        {
            "phase": "post",
            "harness": "claude-code",
            "event": {
                **base,
                "tool_name": "Bash",
                "tool_use_id": "demo-call-1",
                "timestamp": at(3),
                "duration_ms": 42,
            },
        },
        {
            "phase": "denied",
            "harness": "claude-code",
            "event": {
                **base,
                "tool_name": "Bash",
                "tool_use_id": "demo-call-2",
                "reason": "user rejected the command",
                "timestamp": at(4),
            },
        },
        {
            "phase": "post",
            "harness": "claude-code",
            "event": {
                **base,
                "tool_name": "Read",
                "tool_use_id": "demo-call-3",
                "error": "file not found",
                "timestamp": at(5),
            },
        },
    ]


def run_demo(
    store: RecordStore,
    *,
    redaction: RedactionConfig | None = None,
    cwd: str | None = None,
    now: datetime | None = None,
    include_principal: bool = True,
    socket_path: str | None = None,
) -> DemoResult:
    """Drive synthetic events through the real adapter and store, then verify."""
    # Keep at most one demo generation: retire any previous one first (M19 S31).
    purge_demo(store)
    records: list[AgentRecord] = []
    for message in build_messages(now, cwd=cwd, include_principal=include_principal):
        for record in claude_code.normalize(
            message, redaction=redaction, include_principal=include_principal
        ):
            tagged = replace(record, producer=DEMO_PRODUCER)
            store.append(tagged)
            records.append(tagged)

    chain = store.verify()
    kinds: list[str] = []
    for record in records:
        event = record.security_event
        if event is not None and event.type is SecurityEventType.SECRET_DETECTED:
            evidence = event.evidence or {}
            raw_kinds = evidence.get("kinds")
            if isinstance(raw_kinds, list):
                kinds.extend(str(kind) for kind in raw_kinds)
    return DemoResult(
        session_id=DEMO_SESSION_ID,
        records=tuple(records),
        chain_ok=chain.ok,
        chain_checked=chain.checked,
        chain_broken_at=chain.broken_at,
        redaction_kinds=tuple(dict.fromkeys(kinds)),
        daemon_reachable=daemon_reachable(socket_path),
        accepted=sum(1 for r in records if r.outcome.value == "ok"),
        denied=sum(1 for r in records if r.outcome.value == "denied"),
        errored=sum(1 for r in records if r.outcome.value == "error"),
    )


def purge_demo(store: RecordStore) -> int:
    """Tombstone every demo record; the store is left as found, chain intact."""
    if not any(record.session_id == DEMO_SESSION_ID for record in store.records()):
        return 0
    report = store.purge_session(DEMO_SESSION_ID)
    return report.purged


def render_demo(result: DemoResult) -> str:
    """Render the pipeline proof (never a secret value)."""
    lines = ["agentwatch demo — pipeline proof"]
    lines.append(
        "  daemon: reachable"
        if result.daemon_reachable
        else "  daemon: not running (exercised the adapter + store path in-process)"
    )
    lines.append(f"  records: {len(result.records)} (producer.kind: demo)")
    lines.append("  timeline:")
    for record in result.records:
        approval = f" approval={record.approval.value}" if record.approval else ""
        lines.append(f"    {record.tool.name} [{record.outcome.value}]{approval}")
    redaction = ", ".join(result.redaction_kinds) if result.redaction_kinds else "none"
    lines.append(f"  redaction: masked {redaction}")
    verdict = "intact" if result.chain_ok else f"BROKEN at seq {result.chain_broken_at}"
    lines.append(f"  chain: {verdict} ({result.chain_checked} entries checked)")
    lines.append("  clean up with: agentwatch demo --purge")
    return "\n".join(lines)


__all__ = [
    "DEMO_PRODUCER",
    "DEMO_SESSION_ID",
    "DemoResult",
    "build_messages",
    "daemon_reachable",
    "purge_demo",
    "render_demo",
    "run_demo",
]
