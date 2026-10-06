"""LiteLLM / Portkey OTel ingest recipes (M26 GWY-1, #328).

An enterprise routes model traffic through a gateway; the gateway already emits
OTLP with canonical ``gen_ai.*`` spans. The recipe is gateway OTLP export ->
``agentwatch ingest --format otel`` with **no new adapter** (D-Q). These tests
replay committed fixture streams and assert they become validated records.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentwatch.ingest import run_ingest, transcode
from agentwatch.records import validate_record
from agentwatch.store import RecordStore

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ingest"
RECIPE = Path(__file__).resolve().parents[3] / "docs" / "guides" / "gateway-otel-ingest.md"
LITELLM = FIXTURES / "litellm_otlp.json"
PORTKEY = FIXTURES / "portkey_otlp.json"


def _payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_litellm_otlp_stream_ingests_to_records() -> None:
    records, problems = transcode(LITELLM, fmt="otel")

    assert problems == []
    assert records
    for record in records:
        validate_record(record.to_dict())
    assert {record.tool.name for record in records} >= {"chat", "execute_tool"}


def test_portkey_otlp_stream_ingests_to_records() -> None:
    records, problems = transcode(PORTKEY, fmt="otel")

    assert problems == []
    assert records
    assert {record.tool.name for record in records} >= {"chat"}


def test_gateway_streams_chain_into_the_store(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")

    stats = run_ingest([LITELLM, PORTKEY], store, fmt="otel")

    assert stats.records == 3
    assert stats.problems == ()
    assert store.verify().ok


def test_recipe_documentation_ships() -> None:
    assert RECIPE.exists(), "GWY-1 requires the gateway OTel ingest recipe doc"
    text = RECIPE.read_text(encoding="utf-8")
    assert "LiteLLM" in text and "Portkey" in text
    assert "ingest" in text and "gen_ai." in text
