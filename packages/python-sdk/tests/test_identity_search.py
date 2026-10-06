"""Identity search tests (M26 IDN-2, #324).

`search --identity` answers "which records belong to this agent / workload /
on-behalf-of principal" by matching any identity handle on the record, and
matches delegation-chain entries too. Absent identity stays unknown (no match).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.identity import apply_identity_privacy
from agentwatch.query import search
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, RecordPrivacyMode, ToolCall
from agentwatch.store import RecordStore

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(identity: AgentIdentity) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=identity,
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=AT,
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        _record(
            AgentIdentity(
                identity="worker",
                principal="human@corp.example",
                workload_identity="spiffe://corp.example/agent/worker",
                delegation_chain=("orchestrator", "human@corp.example"),
            )
        )
    )
    store.append(_record(AgentIdentity(identity="plain")))
    return store


def test_search_matches_workload_identity(tmp_path: Path) -> None:
    store = _store(tmp_path)

    found = search(store, identity="spiffe://corp.example/agent/worker")

    assert [r.agent.identity for r in found] == ["worker"]


def test_search_matches_a_delegation_chain_entry(tmp_path: Path) -> None:
    store = _store(tmp_path)

    found = search(store, identity="orchestrator")

    assert [r.agent.identity for r in found] == ["worker"]


def test_search_identity_is_case_insensitive_substring(tmp_path: Path) -> None:
    store = _store(tmp_path)

    assert search(store, identity="WORKER")
    assert search(store, identity="does-not-exist") == []


def test_absent_identity_is_not_a_match(tmp_path: Path) -> None:
    store = _store(tmp_path)

    assert [r.agent.identity for r in search(store, identity="plain")] == ["plain"]
    assert search(store, identity="") == []


def test_hashed_principal_is_still_searchable(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    hashed = apply_identity_privacy(
        AgentIdentity(identity="worker", principal="human@corp.example"),
        mode=RecordPrivacyMode.METADATA_ONLY,
    )
    store.append(_record(hashed))

    handle = hashed.principal
    assert handle is not None and handle != "human@corp.example"
    assert [r.agent.identity for r in search(store, identity=handle)] == ["worker"]


def test_cli_search_identity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)

    from agentwatch.cli.main import main

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "search",
            "--identity",
            "orchestrator",
            "--json",
        ]
    )

    assert rc == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["agent"]["identity"] == "worker"
