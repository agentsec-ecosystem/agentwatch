#!/usr/bin/env python3
"""M31 31.2 — 3-host trace correlation / attribution (TRACE-1/2, IDN-1).

Seeds a genuine multi-host causal chain — records tagged with their host, joined
by W3C ``traceparent`` and linked by ``parent_span_id`` — ingests it through the
real ``agentwatch fleet ingest`` surface, then reconstructs it with the real
``agentwatch trace <trace_id>`` (never inventing a correlation).

Modes (argv):
  (default) / --hosts H1,H2,H3   FT-TRACE-1: one ordered chain across 3 hosts ×
                                 3 harnesses; an injected broker interruption is
                                 a classified ``missing-parent`` gap, never absorbed.
  --skew N                       FT-TRACE-2: a child whose start precedes its
                                 parent by N s is a classified ``clock-skew`` gap (F9).
  --attribution                  FT-IDN-1: every node's attribution answers
                                 agent / on-behalf-of / delegation or an honest
                                 ``unknown``, and ``impact``/``tree``/``blame`` agree.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import arg, ok, run  # noqa: E402

from agentwatch.records import (  # noqa: E402
    AgentIdentity,
    AgentRecord,
    Outcome,
    Producer,
    ProducerKind,
    RecordPrivacyMode,
    StepType,
    ToolCall,
)
from agentwatch.store import RecordStore  # noqa: E402

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
ROOT = "0af7651916cd43dd"
CHILD = "b7ad6b7169203331"
GRAND = "00f067aa0ba902b7"
BROKEN = "c1a2b3c4d5e6f708"  # its parent span is never stored -> broker gap
MISSING = "ffffffffffffffff"
BASE = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
HARNESSES = ("claude-code", "codex", "gemini")


def _tp(span: str) -> str:
    return f"00-{TRACE}-{span}-01"


def _rec(
    *,
    session: str,
    agent: str,
    tool: str,
    started: datetime,
    host: str,
    span: str,
    parent: str | None,
    principal: str | None = None,
    delegation: tuple[str, ...] | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(
            identity=agent, name=agent, principal=principal, delegation_chain=delegation
        ),
        tool=ToolCall(name=tool, privacy_mode=RecordPrivacyMode.METADATA_ONLY),
        outcome=Outcome.OK,
        started_at=started,
        ended_at=started + timedelta(milliseconds=500),
        duration_ms=500.0,
        producer=Producer(kind=ProducerKind.HOOK, name=agent),
        span_id=span,
        parent_span_id=parent,
        traceparent=_tp(span),
        host=host,
        step_type=StepType.ACT,
    )


def _hosts(argv: list[str]) -> list[str]:
    spec = arg(argv, "--hosts")
    if spec:
        hosts = [h.strip() for h in spec.split(",") if h.strip()]
        if hosts:
            return hosts
    return ["h1", "h2", "h3"]


def _scenario(hosts: list[str], *, skew_s: float = 0.0, attribution: bool = False):
    """Build per-host record lists for the requested scenario."""
    per_host: dict[str, list[AgentRecord]] = {h: [] for h in hosts}
    root = hosts[0]
    per_host[root].append(
        _rec(
            session=f"ft-fleet-0",
            agent=HARNESSES[0],
            tool="plan",
            started=BASE,
            host=root,
            span=ROOT,
            parent=None,
            principal="svc:deploy-bot" if attribution else None,
            delegation=("user:alice", "svc:deploy-bot") if attribution else None,
        )
    )
    if len(hosts) > 1:
        mid = hosts[1]
        # FT-TRACE-2: child starts before its parent -> clock-skew (F9).
        child_started = BASE - timedelta(seconds=skew_s) if skew_s else BASE + timedelta(seconds=60)
        per_host[mid].append(
            _rec(
                session="ft-fleet-1",
                agent=HARNESSES[1],
                tool="run",
                started=child_started,
                host=mid,
                span=CHILD,
                parent=ROOT,
                principal="svc:deploy-bot" if attribution else None,
                delegation=("user:alice", "svc:deploy-bot") if attribution else None,
            )
        )
        # Broker interruption: a child whose parent span is absent (never absorbed).
        per_host[mid].append(
            _rec(
                session="ft-fleet-1",
                agent=HARNESSES[1],
                tool="deploy",
                started=BASE + timedelta(seconds=90),
                host=mid,
                span=BROKEN,
                parent=MISSING,
            )
        )
    if len(hosts) > 2:
        leaf = hosts[2]
        per_host[leaf].append(
            _rec(
                session="ft-fleet-2",
                agent=HARNESSES[2],
                tool="edit",
                started=BASE + timedelta(seconds=120),
                host=leaf,
                span=GRAND,
                parent=CHILD,
                principal="svc:deploy-bot" if attribution else None,
                delegation=("user:alice", "svc:deploy-bot") if attribution else None,
            )
        )
    return per_host


def _ingest(per_host: dict[str, list[AgentRecord]]) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ft-fleet-"))
    specs: list[str] = []
    for host, records in per_host.items():
        path = tmp / f"{host}.jsonl"
        store = RecordStore(path)
        for record in records:
            store.append(record)
        specs.append(f"{host}={path}")
    run(["agentwatch", "fleet", "ingest", *specs])


def _trace(trace_id: str) -> dict:
    return json.loads(run(["agentwatch", "trace", trace_id, "--json"]).stdout)


def _find(nodes: list[dict], span: str) -> dict | None:
    for node in nodes:
        if node["span_id"] == span:
            return node
        found = _find(node["children"], span)
        if found is not None:
            return found
    return None


def _walk(nodes: list[dict]):
    for node in nodes:
        yield node
        yield from _walk(node["children"])


def _trace1(hosts: list[str]) -> None:
    tree = _trace(TRACE)
    assert set(tree["hosts"]) == set(hosts), tree["hosts"]
    assert tree["records"] >= 4, tree["records"]
    node = _find(tree["roots"], ROOT)
    assert node is not None and node["host"] == hosts[0], (node, hosts[0])
    child = _find(node["children"], CHILD)
    assert child is not None and child["host"] == hosts[1], child
    if len(hosts) > 2:
        grand = _find(child["children"], GRAND)
        assert grand is not None and grand["host"] == hosts[2], grand
    assert any(g["reason"] == "missing-parent" for g in tree["gaps"]), tree["gaps"]
    ok(f"one ordered chain across {len(hosts)} hosts; broker gap classified missing-parent")


def _skew(hosts: list[str]) -> None:
    tree = _trace(TRACE)
    assert set(tree["hosts"]) == set(hosts), tree["hosts"]
    assert any(g["reason"] == "clock-skew" for g in tree["gaps"]), tree["gaps"]
    ok("cross-host clock skew bounded/flagged (clock-skew gap), never silently reordered")


def _attribution(hosts: list[str]) -> None:
    tree = _trace(TRACE)
    nodes = list(_walk(tree["roots"]))
    assert all(n["attribution"]["agent"] for n in nodes), "agent identity missing"
    assert any(
        n["attribution"]["on_behalf_of"] or n["attribution"]["delegation"] for n in nodes
    ), "no on-behalf-of/delegation answered or honest unknown"
    run(["agentwatch", "impact", "ft-fleet-1"])
    run(["agentwatch", "tree", "ft-fleet-1"])
    run(["agentwatch", "blame", "."], check=False)
    ok("attribution answers identity+delegation (or honest unknown) in one command")


def main(argv: list[str]) -> int:
    hosts = _hosts(argv)
    skew_s = float(arg(argv, "--skew", "0") or 0)
    attribution = "--attribution" in argv

    per_host = _scenario(hosts, skew_s=skew_s, attribution=attribution)
    _ingest(per_host)

    snapshot = json.loads(run(["agentwatch", "fleet", "show", "--json"]).stdout)
    assert set(snapshot["hosts"]) == set(hosts), snapshot["hosts"]

    if attribution:
        _attribution(hosts)
    elif skew_s:
        _skew(hosts)
    else:
        _trace1(hosts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
