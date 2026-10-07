"""Cross-org delegation observation + tree/trace extension (M29 A2A-2 #365).

A message handed to a remote agent is recorded as an ``agent-delegation``
observation that extends ``tree``/``trace`` across organization boundaries. The
observation is evidence of an on-behalf-of hop, **never** an authorization
verdict: no approval or authorization source is invented.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agentwatch.adapters import a2a_proxy
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    SecurityEventType,
    ToolCall,
)
from agentwatch.store import RecordStore
from agentwatch.trace import TraceNode, build_trace
from agentwatch.tree import TreeNode, build_tree

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _delegating_frame(**event_overrides: Any) -> dict[str, Any]:
    event: dict[str, Any] = {
        "agent": "remote-scheduler",
        "session_id": "sess-1",
        "direction": "request",
        "remote_org": "Acme",
        "remote_host": "scheduler.acme.example",
        "local_agent": "local-agent",
        "trace_id": "tr-1",
        "parent_span_id": "local-1",
        "rpc": {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "message/send",
            "params": {"message": {"messageId": "m-1", "taskId": "t-1"}},
        },
        "timestamp": "2026-01-02T03:04:05+00:00",
    }
    event.update(event_overrides)
    return {"phase": "a2a", "harness": "a2a-proxy", "event": event}


def _local_record() -> AgentRecord:
    return AgentRecord(
        session_id="sess-1",
        agent=AgentIdentity(identity="local-agent"),
        tool=ToolCall(name="message/send"),
        outcome=Outcome.OK,
        started_at=NOW,
        trace_id="tr-1",
        span_id="local-1",
        host="local-host",
        harness="claude-code",
    )


def _find(node: TraceNode, span: str) -> TraceNode | None:
    if node.span_id == span:
        return node
    for child in node.children:
        found = _find(child, span)
        if found is not None:
            return found
    return None


def test_message_send_to_a_remote_org_emits_an_agent_delegation_observation() -> None:
    records = a2a_proxy.normalize(_delegating_frame())
    delegation = [r for r in records if r.tool.name == "agent-delegation"]

    assert len(delegation) == 1
    observation = delegation[0]
    assert observation.security_event is not None
    assert observation.security_event.type is SecurityEventType.AGENT_DELEGATION
    assert observation.security_event.evidence == {
        "remote_agent": "remote-scheduler",
        "remote_org": "Acme",
        "remote_host": "scheduler.acme.example",
        "message_id": "m-1",
        "task_id": "t-1",
    }


def test_delegation_is_never_an_authorization_verdict() -> None:
    records = a2a_proxy.normalize(_delegating_frame())
    for record in records:
        assert record.authorization is None
        assert record.approval is None


def test_message_send_without_a_remote_org_is_not_cross_org() -> None:
    frame = _delegating_frame()
    del frame["event"]["remote_org"]
    records = a2a_proxy.normalize(frame)

    assert all(record.tool.name != "agent-delegation" for record in records)


def test_trace_extends_across_the_organization_boundary() -> None:
    records = a2a_proxy.normalize(_delegating_frame())

    tree = build_trace([_local_record(), *records], "tr-1")

    assert set(tree.hosts) == {"local-host", "scheduler.acme.example"}
    delegation = _find(tree.roots[0], "a2a:remote-scheduler:7:delegation")
    assert delegation is not None
    assert delegation.host == "scheduler.acme.example"
    assert delegation.tool == "agent-delegation"
    assert delegation.parent_span_id == "a2a:remote-scheduler:7"


def test_tree_attaches_the_remote_agent_under_the_local_caller(tmp_path: Any) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_local_record())
    for record in a2a_proxy.normalize(_delegating_frame()):
        store.append(record)

    root = build_tree(store, "sess-1")

    assert root.key == "local-agent"
    assert [child.key for child in root.children] == ["remote-scheduler"]
    child: TreeNode = root.children[0]
    assert child.tools == 2
    assert "delegation" in child.attribution.label()