"""Cross-host trace reconstruction tests (M26 TRACE-2, #317)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore
from agentwatch.trace import (
    TraceNode,
    build_trace,
    record_trace_id,
    render_trace,
    replay_trace,
    trace_to_json,
)

TRACE = "aa" * 16
T0 = datetime(2026, 1, 2, 10, 0, 0, tzinfo=timezone.utc)


def _record(
    *,
    span: str,
    parent: str | None,
    host: str,
    agent: str,
    tool: str,
    offset_s: float,
    trace: str = TRACE,
) -> AgentRecord:
    started = T0 + timedelta(seconds=offset_s)
    return AgentRecord(
        session_id=f"sess-{host}",
        agent=AgentIdentity(identity=agent),
        tool=ToolCall(name=tool),
        outcome=Outcome.OK,
        started_at=started,
        span_id=span,
        parent_span_id=parent,
        host=host,
        trace_id=trace,
        traceparent=f"00-{trace}-{span}-01",
        harness=host,
    )


def _three_host_records() -> list[AgentRecord]:
    return [
        _record(span="a1", parent=None, host="host-a", agent="planner", tool="plan", offset_s=0),
        _record(
            span="b1", parent="a1", host="host-b", agent="worker", tool="execute_tool", offset_s=5
        ),
        # Host-c's clock is behind: the grandchild appears before its parent.
        _record(
            span="c1",
            parent="b1",
            host="host-c",
            agent="verifier",
            tool="verify",
            offset_s=3,
        ),
    ]


def test_record_trace_id_prefers_the_field_then_traceparent() -> None:
    with_field = _record(
        span="a1", parent=None, host="h", agent="a", tool="t", offset_s=0, trace="bb" * 16
    )
    assert record_trace_id(with_field) == "bb" * 16


def test_build_trace_reconstructs_across_hosts() -> None:
    tree = build_trace(_three_host_records(), TRACE)

    assert tree.records == 3
    assert tree.hosts == ("host-a", "host-b", "host-c")
    root = tree.roots[0]
    assert root.span_id == "a1"
    assert root.children[0].span_id == "b1"
    assert root.children[0].children[0].span_id == "c1"


def test_clock_skew_is_surfaced_not_silently_reordered() -> None:
    tree = build_trace(_three_host_records(), TRACE)

    grandchild = tree.roots[0].children[0].children[0]
    assert grandchild.span_id == "c1"
    # Host-c ran 2 s behind host-b: the edge is flagged, structure is unchanged.
    assert grandchild.skew_ms is not None and grandchild.skew_ms < -1000
    assert any(gap["reason"] == "clock-skew" for gap in tree.gaps)


def test_propagation_break_is_classified_as_an_orphan() -> None:
    records = [
        *_three_host_records(),
        _record(span="d1", parent="missing", host="host-b", agent="drift", tool="x", offset_s=7),
    ]

    tree = build_trace(records, TRACE)

    assert any(gap["reason"] == "missing-parent" for gap in tree.gaps)
    all_spans = _spans(tree.roots)
    assert "d1" in all_spans


def _spans(nodes: tuple[TraceNode, ...]) -> set[str]:
    found: set[str] = set()
    for node in nodes:
        found.add(node.span_id)
        found |= _spans(node.children)
    return found


def test_trace_render_and_json() -> None:
    tree = build_trace(_three_host_records(), TRACE)

    rendered = render_trace(tree)
    assert "host-a" in rendered and "host-c" in rendered
    payload = trace_to_json(tree)
    assert payload["trace_id"] == TRACE
    assert payload["hosts"] == ["host-a", "host-b", "host-c"]
    json.dumps(payload)  # serializable


def test_replay_trace_expands_a_session_across_hosts() -> None:
    records = _three_host_records()
    expanded = replay_trace(records, "sess-host-a")

    assert {record.host for record in expanded} == {"host-a", "host-b", "host-c"}
    assert [record.span_id for record in expanded] == ["a1", "c1", "b1"]


def test_cli_trace(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    for record in _three_host_records():
        store.append(record)

    from agentwatch.cli.main import main

    rc = main(["--set", f"store.path={store_dir}", "trace", TRACE, "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["trace_id"] == TRACE
    assert payload["records"] == 3
