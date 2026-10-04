"""`agentwatch cost` tests (M17 S6, #252)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.cost import build_cost, render_cost
from agentwatch.pricing import PRICING_AS_OF, PRICING_VERSION, cost_usd, price_for
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _usage(
    session: str,
    tokens: int,
    model: str | None,
    *,
    minute: int = 0,
    project: str | None = "/repo",
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a", model_version=model),
        tool=ToolCall(name="session-usage"),
        outcome=Outcome.OK,
        started_at=START + timedelta(minutes=minute),
        project=project,
        tokens=tokens,
        step_type=StepType.OBSERVE,
    )


def _tool(session: str, name: str, *, minute: int = 0) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=name),
        outcome=Outcome.OK,
        started_at=START + timedelta(minutes=minute),
        project="/repo",
        step_type=StepType.ACT,
    )


def test_price_matching_and_normalization() -> None:
    assert price_for("claude-3-5-sonnet-20241022") is not None
    assert price_for("anthropic/claude-3-5-sonnet") is not None
    assert price_for("totally-unknown-model") is None
    assert cost_usd(1_000_000, "claude-3-5-sonnet") == 15.0


def test_cost_rolls_up_to_hand_derived_value(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_usage("s1", 1_000_000, "claude-3-5-sonnet"))

    report = build_cost(store, by="session")

    assert report.total_tokens == 1_000_000
    assert report.total_cost_usd == 15.0
    assert report.rows[0].cost_usd == 15.0
    assert report.pricing_version == PRICING_VERSION
    assert report.pricing_as_of == PRICING_AS_OF


def test_unknown_model_is_tokens_only(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_usage("s1", 500, "mystery-model"))

    report = build_cost(store)

    assert report.rows[0].tokens == 500
    assert report.rows[0].cost_usd is None
    assert report.total_cost_usd is None
    assert "mystery-model" in report.unknown_models
    assert report.note is not None and "tokens only" in report.note


def test_cost_by_tool_splits_evenly(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_tool("s1", "Bash"))
    store.append(_tool("s1", "Read", minute=1))
    store.append(_usage("s1", 1_000_000, "claude-3-5-sonnet"))

    report = build_cost(store, by="tool")

    assert {row.key for row in report.rows} == {"Bash", "Read"}
    assert all(row.tokens == 500_000 for row in report.rows)
    assert abs((report.total_cost_usd or 0) - 15.0) < 1e-9


def test_cost_by_model_and_day(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_usage("s1", 1_000_000, "claude-3-5-sonnet", minute=0))
    store.append(_usage("s2", 1_000_000, "gpt-4o", minute=1))

    by_model = build_cost(store, by="model")
    assert {row.key for row in by_model.rows} == {"claude-3-5-sonnet", "gpt-4o"}
    by_day = build_cost(store, by="day")
    assert len(by_day.rows) == 1


def test_cost_since_filters(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_usage("s1", 100, "claude-3-5-sonnet"))

    report = build_cost(store, since="1s", now=START + timedelta(days=10))

    assert report.rows == ()
    assert report.note is not None and "no session-usage" in report.note


def test_cost_no_usage_is_stated(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_tool("s1", "Bash"))
    report = build_cost(store)
    assert report.rows == ()
    assert "no session-usage" in render_cost(report)


def test_cost_invalid_by_raises(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    with pytest.raises(ValueError):
        build_cost(store, by="nonsense")


def test_cli_cost_json_has_pricing_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    store.append(_usage("s1", 1_000_000, "claude-3-5-sonnet"))

    rc = main(["--set", f"store.path={store_dir}", "cost", "--by", "session", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["pricing_version"] == PRICING_VERSION
    assert payload["total_cost_usd"] == 15.0
