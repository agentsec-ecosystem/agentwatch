"""``oversight`` report facts (M29 APV-3, #440).

Authorization mix, sessions by mode, human-prompt approve/reject + latency, and a
cls1 destructive/network/credential × authorization cross-tab — deterministic,
offline, version-stamped. Facts only; ratios always carry a denominator.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.oversight import OVERSIGHT_VERSION, build_oversight, render_oversight
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Authorization,
    AuthorizationEvidence,
    AuthorizationSource,
    Outcome,
    PermissionMode,
    Producer,
    ProducerKind,
    RecordPrivacyMode,
    StepType,
    ToolCall,
)
from agentwatch.store import RecordStore

BASE = datetime(2026, 1, 2, 3, 0, 0, tzinfo=timezone.utc)
HOOK = Producer(kind=ProducerKind.HOOK, name="claude-code")


def _call(
    session: str,
    at: datetime,
    *,
    source: AuthorizationSource,
    command: str | None = None,
    mode: PermissionMode | None = None,
    outcome: Outcome = Outcome.OK,
    span: str | None = None,
) -> AgentRecord:
    arguments = {"command": command} if command is not None else None
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="worker"),
        tool=ToolCall(
            name="Bash", arguments=arguments, privacy_mode=RecordPrivacyMode.TRUNCATED
        ),
        outcome=outcome,
        started_at=at,
        harness="claude-code",
        producer=HOOK,
        span_id=span or f"call-{at.timestamp()}",
        step_type=StepType.OBSERVE,
        authorization=Authorization(
            source=source, evidence=AuthorizationEvidence.HARNESS_NATIVE
        ),
        permission_mode=mode,
    )


def _prompt(session: str, at: datetime, span: str) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="worker"),
        tool=ToolCall(name="permission-prompt", privacy_mode=RecordPrivacyMode.METADATA_ONLY),
        outcome=Outcome.OK,
        started_at=at,
        harness="claude-code",
        producer=HOOK,
        span_id=span,
        step_type=None,
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    # destructive under bypass + classifier; a benign classifier call.
    store.append(
        _call("s1", BASE, source=AuthorizationSource.BYPASS,
              command="rm -rf /tmp/x", mode=PermissionMode.BYPASS_PERMISSIONS)
    )
    store.append(
        _call("s1", BASE + timedelta(seconds=1), source=AuthorizationSource.CLASSIFIER,
              command="rm -rf /tmp/y", mode=PermissionMode.AUTO)
    )
    store.append(
        _call("s1", BASE + timedelta(seconds=2), source=AuthorizationSource.CLASSIFIER,
              command="ls -la", mode=PermissionMode.AUTO)
    )
    # a human prompt -> approved in 0.5s
    store.append(_prompt("s2", BASE + timedelta(seconds=3), "human-1"))
    store.append(
        _call("s2", BASE + timedelta(seconds=3, milliseconds=500),
              source=AuthorizationSource.HUMAN_ONCE, span="human-1")
    )
    return store


def test_report_is_version_stamped_and_offline(tmp_path: Path) -> None:
    report = build_oversight(_store(tmp_path), now=BASE + timedelta(days=1))
    assert report.taxonomy_version == "authz-v2"
    assert report.classifier_version == "cls1"
    assert OVERSIGHT_VERSION == "oversight-v1"
    assert report.generated_at == BASE + timedelta(days=1)


def test_authorization_mix_matches_hand_computed_totals(tmp_path: Path) -> None:
    report = build_oversight(_store(tmp_path))
    mix = {row.source: row.calls for row in report.sources}
    assert mix["bypass"] == 1
    assert mix["classifier"] == 2
    assert mix["human-once"] == 1
    assert report.total_calls == 4
    classifier = next(row for row in report.sources if row.source == "classifier")
    assert classifier.share == 0.5


def test_destructive_authorization_cross_tab(tmp_path: Path) -> None:
    report = build_oversight(_store(tmp_path))
    cells = {(cell.tool_class, cell.source): cell.calls for cell in report.cross_tab}
    assert cells[("command:destructive", "bypass")] == 1
    assert cells[("command:destructive", "classifier")] == 1
    # the benign `ls` is not destructive
    assert ("command:destructive", "human-once") not in cells
    assert report.destructive_total == 2


def test_latency_only_when_both_timestamps_exist(tmp_path: Path) -> None:
    report = build_oversight(_store(tmp_path))
    assert report.human is not None
    assert report.human.prompted == 1
    assert report.human.approved == 1
    assert report.human.approve_rate == 1.0
    assert report.human.latency.decisions == 1
    assert report.human.latency.median_ms == 500.0
    assert "n/a" not in report.human.latency.note


def test_latency_is_na_without_prompts(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_call("s1", BASE, source=AuthorizationSource.CLASSIFIER, command="ls"))
    report = build_oversight(store)
    assert report.human is not None
    assert report.human.prompted == 0
    assert report.human.latency.median_ms is None
    assert "n/a" in report.human.latency.note


def test_sessions_by_starting_and_ending_mode(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_call("s1", BASE, source=AuthorizationSource.RULE, mode=PermissionMode.DEFAULT))
    store.append(
        _call("s1", BASE + timedelta(seconds=1), source=AuthorizationSource.BYPASS,
              mode=PermissionMode.BYPASS_PERMISSIONS)
    )
    report = build_oversight(store)
    (session,) = report.sessions_by_mode
    assert session.start_mode == "default"
    assert session.end_mode == "bypassPermissions"


def test_group_by_day_and_mode(tmp_path: Path) -> None:
    by_mode = build_oversight(_store(tmp_path), by="mode")
    keys = {group.key for group in by_mode.groups}
    assert "bypassPermissions" in keys and "auto" in keys
    by_day = build_oversight(_store(tmp_path), by="day")
    assert {group.key for group in by_day.groups} == {"2026-01-02"}


def test_render_and_json(tmp_path: Path) -> None:
    report = build_oversight(_store(tmp_path))
    payload = report.to_dict()
    json.dumps(payload)
    text = render_oversight(report)
    assert "authorization mix" in text
    assert "destructive" in text


def test_cli_oversight_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)

    from agentwatch.cli.main import main

    rc = main(["--set", f"store.path={store_dir}", "oversight", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_calls"] == 4


def test_digest_includes_oversight(tmp_path: Path) -> None:
    from agentwatch.digest import build_digest, render_digest

    report = build_digest(_store(tmp_path), now=BASE + timedelta(days=1))
    assert report.oversight_calls == 4
    assert "Oversight" in render_digest(report)


def test_compliance_has_art14_oversight_row(tmp_path: Path) -> None:
    from agentwatch.compliance import build_report
    from agentwatch.configuration import AgentwatchConfig

    store = _store(tmp_path)
    report = build_report(store, "eu-ai-act-art14", config=AgentwatchConfig(), now=BASE)
    assert any(control.control == "art14-human-oversight" for control in report.controls)
