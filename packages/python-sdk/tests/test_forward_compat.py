"""Forward-compatibility matrix for stored data (PRD 38 §Q7, issue #224).

A frozen store is committed per released format version and per supported legacy
shape. Every supported one must still **read, verify, replay, and export** in CI;
an unknown format must fail closed. The set grows per release and entries are
removed only at a major.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agentwatch.records import validate_record
from agentwatch.replay import replay_session
from agentwatch.session_export import export_session, parse_ndjson, to_ndjson, verify_export
from agentwatch.store import RecordStore

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "store-versions"
CASES: list[dict[str, Any]] = json.loads(
    (FIXTURES / "manifest.json").read_text(encoding="utf-8")
)["cases"]
SUPPORTED = [case for case in CASES if case["supported"]]
UNSUPPORTED = [case for case in CASES if not case["supported"]]


def _store(case: dict[str, Any]) -> RecordStore:
    return RecordStore(FIXTURES / case["dir"] / "records.jsonl", durability="none")


@pytest.mark.parametrize("case", SUPPORTED, ids=lambda case: case["id"])
def test_supported_store_reads_and_verifies(case: dict[str, Any]) -> None:
    store = _store(case)

    status = store.verify()

    assert status.ok, status
    records = store.records()
    assert records
    for record in records:
        validate_record(record.to_dict())


@pytest.mark.parametrize("case", UNSUPPORTED, ids=lambda case: case["id"])
def test_unknown_format_fails_closed(case: dict[str, Any]) -> None:
    assert _store(case).verify().ok is False


@pytest.mark.parametrize("case", SUPPORTED, ids=lambda case: case["id"])
def test_supported_store_replays(case: dict[str, Any]) -> None:
    records = replay_session(_store(case), "sess-a")

    assert [record.tool.name for record in records] == ["A", "C"]


@pytest.mark.parametrize("case", SUPPORTED, ids=lambda case: case["id"])
def test_supported_store_exports_and_round_trips(case: dict[str, Any]) -> None:
    export = export_session(_store(case), "sess-a")

    assert verify_export(export.rows)
    reparsed = parse_ndjson(to_ndjson(export))
    assert reparsed.session_id == "sess-a"
    assert verify_export(reparsed.rows)


def test_manifest_covers_every_fixture_directory() -> None:
    on_disk = {path.name for path in FIXTURES.iterdir() if path.is_dir()}
    assert on_disk == {case["dir"] for case in CASES}


def test_matrix_has_a_supported_case() -> None:
    assert SUPPORTED
