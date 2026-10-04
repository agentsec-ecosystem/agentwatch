"""Tests for record provenance — the ``producer`` field (M15 S26, #234).

Assert the round-trip, the legacy read default (inferred ``hook``, never written
back silently), and reject-never-coerce for an unknown producer kind (F8).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    Producer,
    ProducerKind,
    RecordValidationError,
    ToolCall,
    effective_producer,
    producer_is_inferred,
    validate_record,
)

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(**overrides: object) -> AgentRecord:
    base: dict[str, object] = {
        "session_id": "sess-1",
        "agent": AgentIdentity(identity="agent-1"),
        "tool": ToolCall(name="Bash"),
        "outcome": Outcome.OK,
        "started_at": START,
        "harness": "claude-code",
    }
    base.update(overrides)
    return AgentRecord(**base)  # type: ignore[arg-type]


def test_producer_round_trips_through_validation() -> None:
    producer = Producer(kind=ProducerKind.PROXY, name="mcp-proxy", version="0.1.0")
    record = _record(producer=producer)
    data = record.to_dict()
    assert data["producer"] == {"kind": "proxy", "name": "mcp-proxy", "version": "0.1.0"}
    again = validate_record(data)
    assert again.producer == producer


def test_producer_omitted_from_dict_when_absent() -> None:
    assert "producer" not in _record().to_dict()


def test_producer_drops_absent_optionals() -> None:
    assert Producer(kind=ProducerKind.SDK).to_dict() == {"kind": "sdk"}


def test_legacy_record_reads_as_inferred_hook() -> None:
    # A record written before the field existed: no ``producer`` key.
    legacy = _record().to_dict()
    assert "producer" not in legacy
    record = validate_record(legacy)
    assert record.producer is None
    assert producer_is_inferred(record)
    inferred = effective_producer(record)
    assert inferred.kind is ProducerKind.HOOK
    assert inferred.name == "claude-code"


def test_effective_producer_prefers_the_stored_value() -> None:
    producer = Producer(kind=ProducerKind.INGEST, name="otel")
    record = _record(producer=producer)
    assert effective_producer(record) == producer
    assert not producer_is_inferred(record)


def test_unknown_producer_kind_is_rejected() -> None:
    data = _record().to_dict()
    data["producer"] = {"kind": "telepathy"}
    with pytest.raises(RecordValidationError):
        validate_record(data)


def test_producer_unknown_key_is_rejected() -> None:
    data = _record().to_dict()
    data["producer"] = {"kind": "hook", "color": "blue"}
    with pytest.raises(RecordValidationError):
        validate_record(data)


def test_producer_kind_must_be_a_string() -> None:
    data = _record().to_dict()
    data["producer"] = {"kind": 1}
    with pytest.raises(RecordValidationError):
        validate_record(data)


def test_import_override_tags_records() -> None:
    from agentwatch.importer import IMPORT_PRODUCER

    assert IMPORT_PRODUCER.kind is ProducerKind.IMPORT


def test_search_filters_by_producer(tmp_path: Path) -> None:
    from agentwatch.query import search
    from agentwatch.store import RecordStore

    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record(producer=Producer(kind=ProducerKind.HOOK, name="claude-code")))
    store.append(_record(producer=Producer(kind=ProducerKind.INGEST, name="otel")))
    store.append(_record())  # legacy -> inferred hook

    hooks = search(store, producer="hook")
    assert len(hooks) == 2
    ingested = search(store, producer="ingest")
    assert len(ingested) == 1
    assert all(effective_producer(r).kind is ProducerKind.INGEST for r in ingested)
    assert search(store, producer="proxy") == []
