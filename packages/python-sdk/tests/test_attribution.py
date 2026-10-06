"""Attribution end-to-end across investigative views (M26 IDN-3, #325).

A multi-agent fixture must answer "which agent, under which credential, on
whose behalf, with what approval" in every view: blame, tree, trace, impact.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agentwatch.blame import build_blame
from agentwatch.impact import build_impact, render_impact
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Approval,
    CredentialClass,
    Outcome,
    StepType,
    ToolCall,
)
from agentwatch.store import RecordStore
from agentwatch.trace import build_trace, render_trace
from agentwatch.tree import build_tree, render_tree

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
TRACE = "aa" * 16


def _rec(
    *,
    agent: AgentIdentity,
    span: str,
    parent: str | None,
    minutes: int,
    approval: Approval,
) -> AgentRecord:
    from datetime import timedelta

    return AgentRecord(
        session_id="s1",
        agent=agent,
        tool=ToolCall(name="Write", arguments={"file_path": "/repo/app.py"}),
        outcome=Outcome.OK,
        started_at=AT + timedelta(minutes=minutes),
        span_id=span,
        parent_span_id=parent,
        trace_id=TRACE,
        traceparent=f"00-{TRACE}-{span}-01",
        harness="claude-code",
        project="/repo",
        step_type=StepType.ACT,
        approval=approval,
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        _rec(
            agent=AgentIdentity(
                identity="orchestrator",
                principal="human@corp.example",
                credential_class=CredentialClass.SVID,
                workload_identity="spiffe://corp.example/agent/orchestrator",
            ),
            span="a1",
            parent=None,
            minutes=0,
            approval=Approval.USER,
        )
    )
    store.append(
        _rec(
            agent=AgentIdentity(
                identity="worker",
                principal="orchestrator",
                credential_class=CredentialClass.SVID,
                delegation_chain=("human@corp.example", "orchestrator"),
            ),
            span="b1",
            parent="a1",
            minutes=1,
            approval=Approval.AUTO,
        )
    )
    return store


def test_blame_reports_attribution(tmp_path: Path) -> None:
    report = build_blame(_store(tmp_path), "/repo/app.py", project="/repo")

    assert report.hits
    hit = report.hits[0]
    assert hit.attribution.credential_class == "svid"
    assert hit.attribution.on_behalf_of == "orchestrator"
    assert hit.attribution.approval == "auto"


def test_tree_reports_attribution(tmp_path: Path) -> None:
    root = build_tree(_store(tmp_path), "s1")
    child = root.children[0]

    assert root.attribution.on_behalf_of == "human@corp.example"
    assert child.attribution.on_behalf_of == "orchestrator"
    assert "worker" in render_tree(root)
    assert "on-behalf-of" in render_tree(root)


def test_trace_reports_attribution(tmp_path: Path) -> None:
    records = _store(tmp_path).records()
    tree = build_trace(records, TRACE)
    child = tree.roots[0].children[0]

    assert tree.roots[0].attribution.approval == "user"
    assert child.attribution.approval == "auto"
    assert child.attribution.delegation == ("human@corp.example", "orchestrator")
    assert "on-behalf-of" in render_trace(tree)


def test_impact_reports_the_session_attribution(tmp_path: Path) -> None:
    report = build_impact(_store(tmp_path), "s1")

    assert report.attribution is not None
    assert report.attribution.on_behalf_of == "orchestrator"
    assert "on-behalf-of" in render_impact(report)
