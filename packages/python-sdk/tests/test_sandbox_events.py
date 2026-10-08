"""Sandbox-boundary events (M30 SBX-1, #476; PRD 57).

Signal availability was verified per harness before building: Claude Code's
CCO-1 OTel vocabulary exposes no sandbox event; Cursor's raw shell hook carries
``sandbox`` but the adapter does not preserve it yet. The record field and event
type are additive and nullable, so a call with no signal stays ``unknown`` —
never counted as unsandboxed. ``oversight`` reports % calls unsandboxed and
denials by class; ``impact`` keeps attempted-but-blocked destinations apart from
contacted ones.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.classify import NETWORK
from agentwatch.cli.main import main
from agentwatch.impact import build_impact, render_impact
from agentwatch.ocsf import ocsf_target
from agentwatch.oversight import (
    SANDBOX_EXPOSURE,
    build_oversight,
    render_oversight,
    sandbox_boundary_event,
    sandbox_exposure_matrix,
)
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordValidationError,
    SecurityEventType,
    StepType,
    ToolCall,
    validate_record,
)
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _rec(
    session: str,
    *,
    tool: str = "Bash",
    outcome: Outcome = Outcome.OK,
    sandbox: bool | None = None,
    arguments: dict[str, object] | None = None,
    minute: int = 0,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=tool, arguments=arguments),
        outcome=outcome,
        started_at=START + timedelta(minutes=minute),
        harness="claude-code",
        step_type=StepType.ACT,
        sandbox=sandbox,
    )


def test_sandbox_field_round_trips_and_validates() -> None:
    record = _rec("s1", sandbox=False)
    data = record.to_dict()
    assert data["sandbox"] is False
    assert AgentRecord.from_dict(data).sandbox is False
    assert validate_record(data).sandbox is False

    bad = dict(data)
    bad["sandbox"] = "yes"
    with pytest.raises(RecordValidationError):
        validate_record(bad)


def test_absent_sandbox_is_not_serialized() -> None:
    assert "sandbox" not in _rec("s1").to_dict()


def test_sandbox_boundary_event_type_and_ocsf_mapping() -> None:
    assert SecurityEventType.SANDBOX_BOUNDARY.value == "sandbox-boundary"
    assert ocsf_target("sandbox-boundary") is not None
    event = sandbox_boundary_event(
        tool="Bash",
        sandboxed=False,
        emitted_at=START,
        denied_destination="https://blocked.example.com",
    )
    assert event.type is SecurityEventType.SANDBOX_BOUNDARY
    assert event.evidence is not None
    assert event.evidence["sandboxed"] is False
    assert event.evidence["denied_destination"] == "https://blocked.example.com"


def test_oversight_reports_percent_unsandboxed(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("s1", sandbox=True, minute=0))
    store.append(_rec("s1", sandbox=True, minute=1))
    store.append(_rec("s1", sandbox=True, minute=2))
    store.append(_rec("s1", sandbox=False, minute=3))

    report = build_oversight(store)

    assert report.sandbox is not None
    assert report.sandbox.calls_with_fact == 4
    assert report.sandbox.unsandboxed == 1
    assert report.sandbox.unsandboxed_share == 0.25
    rendered = render_oversight(report)
    assert "% calls unsandboxed" in rendered
    assert "1/4" in rendered


def test_oversight_counts_unknown_separately(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("s1", minute=0))
    store.append(_rec("s1", minute=1))

    report = build_oversight(store)

    assert report.sandbox is not None
    assert report.sandbox.calls_with_fact == 0
    assert report.sandbox.unknown == 2
    assert report.sandbox.unsandboxed_share is None


def test_oversight_counts_denials_by_class(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        _rec(
            "s1",
            outcome=Outcome.DENIED,
            sandbox=False,
            arguments={"command": "curl https://blocked.example.com/x"},
        )
    )

    report = build_oversight(store)

    assert report.sandbox is not None
    assert report.sandbox.denials == 1
    assert dict(report.sandbox.denials_by_class).get(NETWORK) == 1
    assert f"denied {NETWORK}: 1" in render_oversight(report)


def test_impact_separates_blocked_from_contacted(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        _rec(
            "s1",
            outcome=Outcome.OK,
            arguments={"command": "curl https://ok.example.com/a"},
        )
    )
    store.append(
        _rec(
            "s1",
            outcome=Outcome.DENIED,
            arguments={"command": "curl https://blocked.example.com/b"},
        )
    )

    report = build_impact(store, "s1")

    contacted = {entry.target for entry in report.network}
    blocked = {entry.target for entry in report.blocked_network}
    assert "https://ok.example.com/a" in contacted
    assert "https://blocked.example.com/b" in blocked
    assert "https://blocked.example.com/b" not in contacted
    assert "network (blocked attempts)" in render_impact(report)


def test_exposure_matrix_is_published_and_honest() -> None:
    matrix = sandbox_exposure_matrix()
    assert {row.harness for row in matrix} == {"claude-code", "cursor", "codex-cli", "gemini-cli"}
    assert next(row for row in matrix if row.harness == "claude-code").status == "none"
    assert next(row for row in matrix if row.harness == "cursor").status == "partial"

    doc = (
        Path(__file__).resolve().parents[3] / "docs" / "reference" / "compatibility.md"
    ).read_text(encoding="utf-8")
    assert "sandbox" in doc.lower()
    for row in SANDBOX_EXPOSURE:
        assert row.harness in doc
        assert row.status in doc


def test_cli_oversight_reports_sandbox(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("s1", sandbox=True, minute=0))
    store.append(_rec("s1", sandbox=False, minute=1))

    rc = main(["--set", f"store.path={tmp_path}", "oversight", "--json"])

    assert rc == 0
    document = json.loads(capsys.readouterr().out)
    assert document["sandbox"]["unsandboxed"] == 1
    assert document["sandbox"]["calls_with_fact"] == 2
