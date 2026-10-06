"""Exact gateway cost attribution tests (M26 GWY-2, #329).

Gateway records carry exact token/cost metadata; `cost` prefers those numbers
over the pricing table and stamps each row exact vs estimated.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agentwatch.cost import build_cost, render_cost
from agentwatch.ingest import transcode_otel
from agentwatch.pricing import USAGE_TOOL
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _gateway_payload() -> dict[str, object]:
    return {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "spanId": "gw-1",
                                "traceId": "gwtrace-1",
                                "name": "chat",
                                "startTimeUnixNano": "1767000000000000000",
                                "endTimeUnixNano": "1767000001000000000",
                                "attributes": [
                                    {"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
                                    {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}},
                                    {
                                        "key": "gen_ai.conversation.id",
                                        "value": {"stringValue": "s-gw"},
                                    },
                                    {
                                        "key": "gen_ai.usage.total_tokens",
                                        "value": {"intValue": "1000"},
                                    },
                                    {"key": "gen_ai.usage.cost", "value": {"doubleValue": 0.05}},
                                ],
                            }
                        ]
                    }
                ]
            }
        ]
    }


def _record(session: str, *, tool: str, tokens: int, cost: float | None, model: str | None) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent", model_version=model),
        tool=ToolCall(name=tool),
        outcome=Outcome.OK,
        started_at=AT,
        tokens=tokens,
        cost_usd=cost,
    )


def test_ingest_captures_exact_gateway_usage() -> None:
    records, problems = transcode_otel(_gateway_payload(), source="litellm")

    assert problems == []
    assert records[0].tokens == 1000
    assert records[0].cost_usd == 0.05


def test_cost_prefers_exact_numbers_and_stamps_the_source(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s-gw", tool="chat", tokens=1000, cost=0.05, model="gpt-4o"))
    store.append(_record("s-est", tool=USAGE_TOOL, tokens=2000, cost=None, model="gpt-4o"))

    report = build_cost(store, by="session")
    rows = {row.key: row for row in report.rows}

    assert rows["s-gw"].cost_usd == 0.05
    assert rows["s-gw"].cost_source == "exact"
    assert rows["s-est"].cost_source == "estimated"
    assert "exact" in render_cost(report)
    assert report.to_dict()["rows"][0]["cost_source"] in {"exact", "estimated"}


def test_cost_source_is_reported_in_json(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s-gw", tool="chat", tokens=1000, cost=0.05, model="gpt-4o"))

    payload = build_cost(store, by="session").to_dict()

    row = payload["rows"][0]
    assert row["cost_source"] == "exact"
    assert payload["total_cost_source"] == "exact"
