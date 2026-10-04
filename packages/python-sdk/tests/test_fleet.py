"""Fleet aggregation tests (M11 R13)."""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.fleet import (
    FleetSource,
    aggregate,
    build_fleet,
    fleet_to_json,
    ingest_host,
    parse_sources,
    render_fleet,
)
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    SecurityEvent,
    SecurityEventType,
    StepType,
    ToolCall,
)
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(
    *,
    session: str = "s1",
    span: str | None = "sp1",
    agent: str = "agent-1",
    version: str | None = "1.0",
    outcome: Outcome = Outcome.OK,
    duration: float | None = None,
    event: bool = False,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity=agent, version=version),
        tool=ToolCall(name="Bash"),
        outcome=outcome,
        started_at=START,
        span_id=span,
        duration_ms=duration,
        step_type=StepType.ACT,
        security_event=(
            SecurityEvent(
                type=SecurityEventType.SECRET_DETECTED, emitted_at=START, emitter="agentwatch"
            )
            if event
            else None
        ),
    )


def _host_store(path: Path, records: list[AgentRecord]) -> Path:
    store = RecordStore(path)
    for record in records:
        store.append(record)
    return path


def test_parse_sources_round_trips(tmp_path: Path) -> None:
    sources = parse_sources([f"host-a={tmp_path / 'a.jsonl'}"])
    assert sources == [FleetSource(host="host-a", records_path=tmp_path / "a.jsonl")]
    with pytest.raises(ValueError):
        parse_sources(["missing-equals"])


def test_ingest_host_tags_and_chains(tmp_path: Path) -> None:
    host_path = _host_store(tmp_path / "a.jsonl", [_record(), _record(session="s2", span="sp2")])
    store = RecordStore(tmp_path / "fleet.jsonl")

    stats = ingest_host(FleetSource("host-a", host_path), store)

    assert stats.records == 2
    assert stats.duplicates == 0
    assert {record.host for record in store.records()} == {"host-a"}
    assert store.verify().ok


def test_ingest_host_is_idempotent(tmp_path: Path) -> None:
    host_path = _host_store(tmp_path / "a.jsonl", [_record()])
    store = RecordStore(tmp_path / "fleet.jsonl")

    ingest_host(FleetSource("host-a", host_path), store)
    second = ingest_host(FleetSource("host-a", host_path), store)

    assert second.records == 0
    assert second.duplicates == 1
    assert len(store.records()) == 1


def test_ingest_missing_host_store_is_reported(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "fleet.jsonl")
    stats = ingest_host(FleetSource("ghost", tmp_path / "nope.jsonl"), store)
    assert stats.missing
    assert stats.records == 0


def test_aggregate_groups_by_host_and_agent(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "fleet.jsonl")
    _host_store(
        tmp_path / "a.jsonl",
        [
            _record(session="s1", span="a1", outcome=Outcome.OK, duration=10.0),
            _record(session="s2", span="a2", outcome=Outcome.ERROR, duration=20.0, event=True),
            _record(session="s3", span="a3", outcome=Outcome.DENIED),
        ],
    )
    _host_store(tmp_path / "b.jsonl", [_record(session="s4", span="b1", agent="agent-2")])
    ingest_host(FleetSource("host-a", tmp_path / "a.jsonl"), store)
    ingest_host(FleetSource("host-b", tmp_path / "b.jsonl"), store)

    snapshot = build_fleet(store)
    by_host = {rollup.host: rollup for rollup in snapshot.rollups}

    assert snapshot.total_records == 4
    assert set(snapshot.hosts) == {"host-a", "host-b"}
    host_a = by_host["host-a"]
    assert (host_a.total, host_a.ok, host_a.error, host_a.denied) == (3, 1, 1, 1)
    assert host_a.security_events == 1
    assert host_a.avg_duration_ms == 15.0
    assert by_host["host-b"].agent == "agent-2"


def test_aggregate_can_ignore_host() -> None:
    rollups = aggregate(
        [_record(session="s1", span="a1"), _record(session="s2", span="a2")],
        group_by_host=False,
    )
    assert len(rollups) == 1
    assert rollups[0].host is None
    assert rollups[0].total == 2


def test_render_and_json_shapes(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "fleet.jsonl")
    _host_store(tmp_path / "a.jsonl", [_record(duration=5.0)])
    ingest_host(FleetSource("host-a", tmp_path / "a.jsonl"), store)

    snapshot = build_fleet(store)
    text = render_fleet(snapshot)
    assert "HOST\tAGENT" in text
    assert "host-a" in text
    payload = fleet_to_json(snapshot)
    assert payload["hosts"] == ["host-a"]
    assert payload["rollups"][0]["avg_duration_ms"] == 5.0


def test_cli_fleet_ingest_then_show(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main = importlib.import_module("agentwatch.cli.main")
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path / "fleet"))
    host_a = _host_store(tmp_path / "a.jsonl", [_record()])
    host_b = _host_store(tmp_path / "b.jsonl", [_record(session="s2", span="b1")])

    assert main.main(["fleet", "ingest", f"host-a={host_a}", f"host-b={host_b}"]) == 0
    capsys.readouterr()  # drop the ingest summary
    assert main.main(["fleet", "show", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert set(payload["hosts"]) == {"host-a", "host-b"}
    assert payload["total_records"] == 2
