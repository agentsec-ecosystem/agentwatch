"""TypeScript schema-portability spike (M28 TSS-1, #368; PRD 46 §TSS-1).

The decision (a shipped TS SDK at v0.3.0) is recorded in ADR-0049. This spike
proves the *portability* premise: the JSON Schema in `schema/` generates usable
TypeScript types, and a real v0.2.0 record round-trips through the schema and
appears in the generated types. Shipping the SDK is explicitly deferred.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_ts_types.py"
SCHEMA = ROOT / "schema" / "agent-record.schema.json"
ADR = ROOT / "docs" / "adr" / "0049-typescript-sdk-decision.md"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_ts_types", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def _interface(ts: str, name: str) -> str:
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", ts, re.DOTALL)
    assert match is not None, f"missing interface {name}"
    return match.group(1)


def test_generates_typescript_interfaces() -> None:
    ts = _module().generate_typescript(_schema())

    assert "export interface AgentRecord" in ts
    assert "session_id" in _interface(ts, "AgentRecord")


def test_enums_become_union_types() -> None:
    ts = _module().generate_typescript(_schema())

    assert "pre_execution" in ts
    assert "post_execution" in ts
    assert "ambient/shared" in ts or "api-key" in ts


def test_a_v0_2_0_record_round_trips_through_the_schema() -> None:
    schema = _schema()
    record = {
        "schema_version": "0.2.0",
        "session_id": "s1",
        "agent": {"identity": "agent", "credential_class": "ambient/shared"},
        "tool": {"name": "Bash"},
        "outcome": "ok",
        "started_at": "2026-10-06T12:00:00Z",
        "record_phase": "post_execution",
    }

    jsonschema.validate(record, schema)

    ts = _module().generate_typescript(schema)
    agent = _interface(ts, "AgentRecord")
    for key in record:
        assert re.search(rf"\b{key}\??:", agent), f"{key} missing from generated AgentRecord"
    for key in record["agent"]:
        assert re.search(rf"\b{key}\??:", _interface(ts, "AgentRecordAgent"))


def test_the_decision_is_recorded_and_shipping_is_deferred() -> None:
    text = ADR.read_text(encoding="utf-8")

    assert "v0.3.0" in text
    assert "deferred" in text.lower()
    assert "TypeScript" in text
