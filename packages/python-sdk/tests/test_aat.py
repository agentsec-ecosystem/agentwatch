"""AAT export mapping tests (M25 AAT-1/AAT-2, #295/#296)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.aat import (
    AAT_DRAFT,
    AAT_MAPPING,
    aat_record,
    export_aat,
    to_aat_json,
    verify_aat,
)
from agentwatch.cli.main import main
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    CredentialClass,
    Outcome,
    RecordPhase,
    StepType,
    ToolCall,
    validate_record,
)
from agentwatch.session_export import export_session
from agentwatch.store import RecordStore

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(phase: RecordPhase | None = RecordPhase.PRE_EXECUTION) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(
            identity="agent-1",
            name="triage",
            version="1.0",
            workload_identity="spiffe://corp.example/agent/triage",
            credential_class=CredentialClass.SVID,
            principal="hmac-sha256:abc",
        ),
        tool=ToolCall(name="Bash", privacy_mode=None),
        outcome=Outcome.DENIED,
        started_at=AT,
        harness="claude-code",
        step_type=StepType.ACT,
        record_phase=phase,
    )


def _store(path: Path) -> RecordStore:
    store = RecordStore(path)
    store.append(_record())
    return store


def test_mapping_table_documents_every_emitted_concept() -> None:
    entry = aat_record(_record(), seq=0, prev_hash="g", hash="h")
    for concept in AAT_MAPPING:
        assert concept in entry


def test_record_shape_and_phase() -> None:
    entry = aat_record(_record(), seq=3, prev_hash="p", hash="h")

    assert entry["aat_version"] == AAT_DRAFT
    assert entry["action_type"] == "act"
    assert entry["outcome"] == "denied"
    assert entry["record_phase"] == "pre_execution"
    assert entry["agent"]["workload_identity"] == "spiffe://corp.example/agent/triage"
    assert entry["agent"]["credential_class"] == "svid"
    assert entry["chain"] == {"seq": 3, "prev_hash": "p", "hash": "h"}
    # Fields we cannot populate are surfaced, never invented.
    assert entry["unmapped"]["response_hash"]
    assert entry["unmapped"]["response_size"]


def test_legacy_record_phase_is_unknown() -> None:
    entry = aat_record(_record(phase=None), seq=0, prev_hash="g", hash="h")
    assert entry["record_phase"] == "unknown"


def test_export_bundle_and_coverage(tmp_path: Path) -> None:
    export = export_session(_store(tmp_path / "records.jsonl"), "s1")
    bundle = export_aat(export, privacy_mode="metadata-only")

    assert bundle["aat_version"] == AAT_DRAFT
    assert bundle["session_id"] == "s1"
    assert bundle["coverage"]["records"] == 1
    assert bundle["coverage"]["privacy_mode"] == "metadata-only"
    assert verify_aat(bundle) is True


def test_verify_detects_tampering(tmp_path: Path) -> None:
    export = export_session(_store(tmp_path / "records.jsonl"), "s1")
    bundle = export_aat(export, privacy_mode="metadata-only")
    bundle["records"][0]["agentwatch"]["outcome"] = "ok"

    assert verify_aat(bundle) is False


def test_export_is_lossless(tmp_path: Path) -> None:
    export = export_session(_store(tmp_path / "records.jsonl"), "s1")
    bundle = export_aat(export, privacy_mode="metadata-only")

    # The native record is embedded and still validates against the schema.
    validate_record(bundle["records"][0]["agentwatch"])


def test_to_aat_json_is_deterministic() -> None:
    bundle = {"schema": "x", "records": []}
    assert to_aat_json(bundle) == to_aat_json(bundle)


def test_cli_export_session_aat(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir / "records.jsonl")

    rc = main(["--set", f"store.path={store_dir}", "export-session", "s1", "--format", "aat"])
    assert rc == 0
    bundle = json.loads(capsys.readouterr().out)
    assert bundle["aat_version"] == AAT_DRAFT
    assert verify_aat(bundle)


def test_cli_export_session_aat_to_file(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir / "records.jsonl")
    out = tmp_path / "aat.json"

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "export-session",
            "s1",
            "--format",
            "aat",
            "--output",
            str(out),
        ]
    )

    assert rc == 0
    assert verify_aat(json.loads(out.read_text(encoding="utf-8")))