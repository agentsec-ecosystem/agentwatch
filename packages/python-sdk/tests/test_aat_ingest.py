"""AAT ingest tests (M26 AAT-3, #313).

Foreign AAT bundles are untrusted input: the chain must validate before any
record is stored (fail closed), and a record that cannot be normalized is
quarantined with a reason (B4) — never dropped silently and never stored.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from agentwatch.aat import AAT_DRAFT, export_aat, to_aat_json
from agentwatch.cli.main import main
from agentwatch.ingest import run_ingest
from agentwatch.quarantine import QuarantineLog
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPhase,
    StepType,
    ToolCall,
)
from agentwatch.session_export import export_session
from agentwatch.store import RecordStore

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(
    *,
    span_id: str | None = "sp-1",
    arguments: dict[str, Any] | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="agent-1", name="triage"),
        tool=ToolCall(name="Bash", arguments=arguments),
        outcome=Outcome.DENIED,
        started_at=AT,
        span_id=span_id,
        harness="claude-code",
        step_type=StepType.ACT,
        record_phase=RecordPhase.PRE_EXECUTION,
    )


def _source_bundle(tmp_path: Path, records: list[AgentRecord]) -> dict[str, Any]:
    store = RecordStore(tmp_path / "source.jsonl")
    for record in records:
        store.append(record)
    return export_aat(export_session(store, "s1"), privacy_mode="metadata-only")


def _write(tmp_path: Path, bundle: dict[str, Any]) -> Path:
    path = tmp_path / "foreign.aat.json"
    path.write_text(to_aat_json(bundle), encoding="utf-8")
    return path


def _rehash(entry: dict[str, Any]) -> None:
    """Recompute an entry's chain hash over its (possibly edited) native record."""
    native = entry["agentwatch"]
    canonical = json.dumps(native, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    entry["chain"]["hash"] = hashlib.sha256(
        (entry["chain"]["prev_hash"] + canonical).encode("utf-8")
    ).hexdigest()


def test_ingest_aat_round_trips_records(tmp_path: Path) -> None:
    bundle = _source_bundle(tmp_path, [_record()])
    store = RecordStore(tmp_path / "records.jsonl")

    stats = run_ingest([_write(tmp_path, bundle)], store, fmt="aat")

    assert stats.records == 1
    assert stats.problems == ()
    assert store.verify().ok
    stored = store.records()
    assert len(stored) == 1
    assert stored[0].tool.name == "Bash"
    assert stored[0].agent.identity == "agent-1"
    assert stored[0].outcome is Outcome.DENIED
    assert stored[0].record_phase is RecordPhase.PRE_EXECUTION


def test_ingest_aat_rejects_tampered_chain(tmp_path: Path) -> None:
    bundle = _source_bundle(tmp_path, [_record()])
    bundle["records"][0]["agentwatch"]["outcome"] = "ok"  # breaks the foreign chain hash
    quarantine = QuarantineLog(tmp_path / "quarantine.jsonl")
    store = RecordStore(tmp_path / "records.jsonl")

    stats = run_ingest([_write(tmp_path, bundle)], store, fmt="aat", quarantine=quarantine)

    assert stats.records == 0
    assert stats.problems
    assert store.records() == []
    entries = quarantine.entries()
    assert entries
    assert "chain" in entries[0]["reason"]


def test_ingest_aat_quarantines_a_non_normalizable_record(tmp_path: Path) -> None:
    bundle = _source_bundle(tmp_path, [_record(span_id="a"), _record(span_id="b")])
    # A record whose chain hash is internally consistent but whose native payload
    # cannot be normalized (missing the required ``outcome``).
    del bundle["records"][1]["agentwatch"]["outcome"]
    _rehash(bundle["records"][1])
    quarantine = QuarantineLog(tmp_path / "quarantine.jsonl")
    store = RecordStore(tmp_path / "records.jsonl")

    stats = run_ingest([_write(tmp_path, bundle)], store, fmt="aat", quarantine=quarantine)

    assert stats.records == 1  # the valid sibling is still stored
    assert any("non-normalizable" in p.reason for p in stats.problems)
    assert len(store.records()) == 1
    entries = quarantine.entries()
    assert entries
    assert "non-normalizable" in entries[0]["reason"]


def test_ingest_aat_rejects_an_unsupported_revision(tmp_path: Path) -> None:
    bundle = _source_bundle(tmp_path, [_record()])
    bundle["aat_version"] = "draft-sharif-agent-audit-trail-99"
    store = RecordStore(tmp_path / "records.jsonl")

    stats = run_ingest([_write(tmp_path, bundle)], store, fmt="aat")

    assert stats.records == 0
    assert stats.problems
    assert store.records() == []


def test_ingest_aat_redacts_foreign_secrets(tmp_path: Path) -> None:
    bundle = _source_bundle(tmp_path, [_record(arguments={"token": "sk-abcdefgh1234"})])
    store = RecordStore(tmp_path / "records.jsonl")

    stats = run_ingest([_write(tmp_path, bundle)], store, fmt="aat")

    assert stats.records == 1
    dumped = json.dumps(store.records()[0].to_dict())
    assert "sk-abcdefgh1234" not in dumped
    assert "REDACTED" in dumped


def test_cli_ingest_aat_records_into_the_store(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path / "store"))
    bundle = _source_bundle(tmp_path, [_record()])
    path = _write(tmp_path, bundle)

    rc = main(["ingest", str(path), "--format", "aat", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["records"] == 1
    assert (tmp_path / "store" / "records.jsonl").exists()
