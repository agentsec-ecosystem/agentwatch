"""`agentwatch tree` tests (M17 S17, #245)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore
from agentwatch.tree import build_tree, render_tree, sort_by_cost

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _rec(
    identity: str,
    tool: str,
    *,
    minute: int,
    span: str | None = None,
    parent_span: str | None = None,
    outcome: Outcome = Outcome.OK,
    cost: float | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity=identity),
        tool=ToolCall(name=tool),
        outcome=outcome,
        started_at=START + timedelta(minutes=minute),
        span_id=span,
        parent_span_id=parent_span,
        step_type=StepType.ACT,
        cost_usd=cost,
    )


def _fanout_store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("root", "Task", minute=0, span="t1"))
    store.append(_rec("root", "Task", minute=1, span="t2"))
    store.append(_rec("sub-1", "Bash", minute=2, span="b1", parent_span="t1", cost=5.0))
    store.append(_rec("sub-2", "Read", minute=3, span="r1", parent_span="t2", cost=1.0))
    return store


def test_two_parallel_subagents_are_siblings(tmp_path: Path) -> None:
    root = build_tree(_fanout_store(tmp_path), "s1")

    assert root.key == "root"
    assert [child.key for child in root.children] == ["sub-1", "sub-2"]
    sub1 = next(child for child in root.children if child.key == "sub-1")
    assert sub1.tools == 1
    assert sub1.outcomes == {"ok": 1}
    assert sub1.orphan is False


def test_no_subagent_renders_one_root(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("root", "Bash", minute=0, span="b1"))

    root = build_tree(store, "s1")

    assert root.key == "root"
    assert root.children == ()
    assert root.tools == 1
    assert "agentwatch tree root" in render_tree(root)


def test_orphan_is_attached_to_root(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("root", "Task", minute=0, span="t1"))
    store.append(_rec("ghost", "Bash", minute=1, span="g1", parent_span="missing"))

    root = build_tree(store, "s1")

    ghost = next(child for child in root.children if child.key == "ghost")
    assert ghost.orphan is True
    assert "orphan" in render_tree(root)


def test_by_cost_orders_siblings(tmp_path: Path) -> None:
    root = build_tree(_fanout_store(tmp_path), "s1")
    ordered = sort_by_cost(root)
    assert [child.key for child in ordered.children] == ["sub-1", "sub-2"]


def test_no_records_is_empty_root(tmp_path: Path) -> None:
    root = build_tree(RecordStore(tmp_path / "records.jsonl"), "s1")
    assert root.tools == 0
    assert root.children == ()


def test_cli_tree_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    source = _fanout_store(tmp_path)
    import shutil

    shutil.copy(source.path, store_dir / "records.jsonl")

    rc = main(["--set", f"store.path={store_dir}", "tree", "s1", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["key"] == "root"
    assert [child["key"] for child in payload["children"]] == ["sub-1", "sub-2"]
