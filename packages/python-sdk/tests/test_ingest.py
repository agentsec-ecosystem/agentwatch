"""OTel / NDJSON ingestion tests (M10 N2 #213)."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from agentwatch.ingest import (
    run_ingest,
    transcode_ndjson,
    transcode_otel,
)
from agentwatch.quarantine import QuarantineLog
from agentwatch.records import SecurityEventType, validate_record
from agentwatch.redact import redaction_config_from_mode
from agentwatch.store import RecordStore

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ingest"
TRACE = FIXTURES / "otel_trace.json"


def _payload() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(TRACE.read_text(encoding="utf-8"))
    return data


def test_transcode_otel_chains_and_validates() -> None:
    records, problems = transcode_otel(_payload())

    assert len(records) == 2
    assert len(problems) == 1  # the unmappable span is reported, never dropped
    for record in records:
        validate_record(record.to_dict())
    assert records[0].tool.name == "get_weather"
    assert records[0].session_id == "conv-1"
    assert records[0].span_id == "otel:sp-1"
    assert records[0].agent.identity == "weather-bot"
    assert records[1].outcome.value == "error"
    assert records[1].security_event is not None
    assert records[1].security_event.type is SecurityEventType.SECRET_DETECTED


def test_secret_is_masked_when_content_captured() -> None:
    records, _ = transcode_otel(_payload(), redaction=redaction_config_from_mode("full"))

    dumped = " ".join(str(record.to_dict()) for record in records)
    assert "sk-abcdefgh1234" not in dumped
    assert "REDACTED" in dumped


def test_run_ingest_chains_into_store(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    stats = run_ingest([TRACE], store, fmt="otel")

    assert stats.records == 2
    assert len(stats.problems) == 1
    assert store.verify().ok
    assert len(store.records()) == 2


def test_unmappable_input_is_quarantined(tmp_path: Path) -> None:
    quarantine = QuarantineLog(tmp_path / "quarantine.jsonl")
    store = RecordStore(tmp_path / "records.jsonl")

    stats = run_ingest([TRACE], store, fmt="otel", quarantine=quarantine)

    assert stats.problems
    entries = quarantine.entries()
    assert entries
    assert "unmappable" in entries[0]["reason"]


def test_run_ingest_is_idempotent(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    run_ingest([TRACE], store, fmt="otel")
    second = run_ingest([TRACE], store, fmt="otel")

    assert second.records == 0
    assert second.duplicates == 2
    assert len(store.records()) == 2


def test_ndjson_ingests_one_span_per_line() -> None:
    span = _payload()["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    text = json.dumps(span) + "\n" + "not json\n"

    records, problems = transcode_ndjson(text)

    assert len(records) == 1
    assert records[0].tool.name == "get_weather"
    assert len(problems) == 1


def test_span_ids_are_namespaced_by_source() -> None:
    span = _payload()["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    first, _ = transcode_otel(span, source="source-a")
    second, _ = transcode_otel(span, source="source-b")

    assert first[0].span_id != second[0].span_id
    assert first[0].span_id == "source-a:sp-1"


def test_invalid_json_reports_a_problem() -> None:
    records, problems = transcode_ndjson("{not json}")

    assert records == []
    assert problems and "invalid JSON" in problems[0].reason


def test_cli_ingest_records_into_the_store(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path))
    main = importlib.import_module("agentwatch.cli.main")

    rc = main.main(["ingest", str(TRACE), "--format", "otel", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["records"] == 2
    assert (tmp_path / "records.jsonl").exists()
    assert (tmp_path / "quarantine.jsonl").exists()
