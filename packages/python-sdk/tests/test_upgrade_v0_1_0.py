"""MIG-1 — upgrade a frozen v0.1.0 store to v0.2.0 (M28, #436; PRD 9).

The v0.2.0 schema is additive (W5): a store written by v0.1.0 keeps verifying and
keeps being readable, and a v0.2.0 record (with the new identity fields) can be
appended while the chain stays green. This freezes that promise against a
committed v0.1.0 store vector.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    CredentialClass,
    Outcome,
    ToolCall,
)
from agentwatch.store import RecordStore

ROOT = Path(__file__).resolve().parents[3]
FROZEN_V0_1_0 = ROOT / "schema" / "vectors" / "store" / "valid.jsonl"

NOW = datetime(2026, 10, 6, 12, 0, 0, tzinfo=timezone.utc)


def _upgraded_store(tmp_path: Path) -> RecordStore:
    dest = tmp_path / "records.jsonl"
    shutil.copy(FROZEN_V0_1_0, dest)
    return RecordStore(dest)


def test_frozen_v0_1_0_store_still_verifies() -> None:
    # The committed vector is a v0.1.0 store; opening it with the v0.2.0 SDK
    # must not require a rewrite.
    assert RecordStore(FROZEN_V0_1_0).verify().ok is True


def test_frozen_v0_1_0_records_read_with_an_honest_default(tmp_path: Path) -> None:
    store = _upgraded_store(tmp_path)

    records = store.records()

    assert records, "the frozen store carries records"
    assert all(record.schema_version == "0.1.0" for record in records)
    # Fields absent from v0.1.0 are honest ``None``/empty, never invented.
    assert all(record.agent.credential_class is None for record in records)


def test_v0_2_0_record_appends_without_breaking_the_chain(tmp_path: Path) -> None:
    store = _upgraded_store(tmp_path)

    store.append(
        AgentRecord(
            session_id="migrated",
            agent=AgentIdentity(
                identity="agent",
                credential_class=CredentialClass.AMBIENT_SHARED,
            ),
            tool=ToolCall(name="Bash"),
            outcome=Outcome.OK,
            started_at=NOW,
        )
    )

    reloaded = RecordStore(tmp_path / "records.jsonl")
    assert reloaded.verify().ok is True
    newest = reloaded.records()[-1]
    assert newest.agent.credential_class == CredentialClass.AMBIENT_SHARED
