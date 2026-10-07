"""Claude Compliance API ingest tests (M27 CCA-1 #341).

Consent-first ingest of an Anthropic Compliance API export: actor email → hashed
principal, pulls recorded as ``store-access``, and feed-vs-hook mismatches
classified as ``compliance-discrepancy`` observations (never silently merged).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.compliance_api import classify_discrepancies, read_compliance_export
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, Producer, ProducerKind, ToolCall
from agentwatch.store import RecordStore

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

EXPORT = [
    {
        "id": "act_1",
        "created_at": "2026-01-02T03:04:05Z",
        "type": "claude_code.tool_use",
        "session_id": "s1",
        "organization_id": "org_1",
        "actor": {"type": "user", "email": "human@corp.example", "user_id": "u1"},
        "tool_name": "Bash",
        "outcome": "ok",
    },
    {
        "id": "act_2",
        "created_at": "2026-01-02T03:05:05Z",
        "type": "claude_code.tool_use",
        "session_id": "s1",
        "actor": {"type": "user", "email": "human@corp.example"},
        "outcome": "denied",
    },
]


def _export(tmp_path: Path) -> Path:
    path = tmp_path / "compliance.json"
    path.write_text(json.dumps({"data": EXPORT}), encoding="utf-8")
    return path


def _hook(session: str, span: str, outcome: Outcome) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="claude-code"),
        tool=ToolCall(name="Bash"),
        outcome=outcome,
        started_at=AT,
        span_id=span,
        producer=Producer(kind=ProducerKind.HOOK, name="claude-code"),
    )


def test_reads_events_with_hashed_principal(tmp_path: Path) -> None:
    read = read_compliance_export(_export(tmp_path))

    assert len(read.records) == 2
    first = read.records[0]
    assert first.tool.name == "Bash"
    assert first.session_id == "s1"
    assert first.agent.principal is not None
    assert first.agent.principal != "human@corp.example"
    assert "human@corp.example" not in str(first.to_dict())
    assert read.records[1].outcome is Outcome.ERROR  # "denied"


def test_discrepancies_are_classified_not_merged(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_hook("s1", "act_1", Outcome.ERROR))  # hook says error; feed says ok

    feed = read_compliance_export(_export(tmp_path)).records
    observations, notes = classify_discrepancies(feed, store)

    assert len(observations) == 1
    assert observations[0].tool.name == "compliance-discrepancy"
    assert notes and "hook=error" in notes[0]


def test_cli_requires_consent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from agentwatch.cli.main import main

    rc = main(
        [
            "--set",
            f"store.path={tmp_path}",
            "ingest",
            str(_export(tmp_path)),
            "--format",
            "claude-compliance",
        ]
    )

    assert rc != 0
    assert "consent" in capsys.readouterr().err


def test_cli_consent_records_store_access_and_ingests(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from agentwatch.cli.main import main

    store_dir = tmp_path / "store"
    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "ingest",
            str(_export(tmp_path)),
            "--format",
            "claude-compliance",
            "--consent",
            "--json",
        ]
    )

    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["records"] == 2
    store = RecordStore(store_dir / "records.jsonl")
    names = [record.tool.name for record in store.records()]
    assert "store-access" in names
    assert "Bash" in names
    assert "claude_code.tool_use" in names  # event with no tool_name uses its activity type
