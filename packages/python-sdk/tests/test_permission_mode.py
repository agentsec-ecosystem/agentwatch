"""Permission mode per call + transition records (M29 APV-2, #439).

The active mode is a time-varying fact recorded on every call; every transition
is its own observation, so a ``default -> bypass -> default`` fixture reconstructs
and the bypass interval is flagged in ``impact``. Missing mode data is ``unknown``
and counted in ``coverage`` — never inferred.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agentwatch import claude_otel
from agentwatch.adapters import claude_code
from agentwatch.impact import build_impact
from agentwatch.permission_mode import (
    MODE_CHANGED_TOOL,
    effective_modes,
    is_permission_mode_change,
    mode_intervals,
    permission_mode_change_record,
)
from agentwatch.query import search
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    PermissionMode,
    Producer,
    ProducerKind,
    StepType,
    ToolCall,
    validate_record,
)
from agentwatch.store import RecordStore

BASE = datetime(2026, 1, 2, 3, 0, 0, tzinfo=timezone.utc)


def _call(session: str, at: datetime, *, mode: PermissionMode | None = None) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="worker"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=at,
        harness="claude-code",
        producer=Producer(kind=ProducerKind.HOOK, name="claude-code"),
        span_id=f"call-{at.timestamp()}",
        step_type=StepType.OBSERVE,
        permission_mode=mode,
    )


def _transition(session: str, at: datetime, frm: str, to: str) -> AgentRecord:
    record = permission_mode_change_record(
        session_id=session,
        at=at,
        from_mode=PermissionMode(frm),
        to_mode=PermissionMode(to),
        harness="claude-code",
        producer=Producer(kind=ProducerKind.HOOK, name="claude-code"),
    )
    return record


def test_mode_change_record_is_a_transition_observation() -> None:
    record = _transition("s1", BASE, "default", "bypassPermissions")
    assert record.tool.name == MODE_CHANGED_TOOL
    assert record.step_type is None
    assert is_permission_mode_change(record)
    assert record.permission_mode is PermissionMode.BYPASS_PERMISSIONS
    assert record.tool.arguments == {"from": "default", "to": "bypassPermissions"}
    validate_record(record.to_dict())


def test_default_bypass_default_reconstructs() -> None:
    records = [
        _call("s1", BASE, mode=PermissionMode.DEFAULT),
        _call("s1", BASE + timedelta(seconds=1)),
        _transition("s1", BASE + timedelta(seconds=2), "default", "bypassPermissions"),
        _call("s1", BASE + timedelta(seconds=3)),
        _call("s1", BASE + timedelta(seconds=4)),
        _transition("s1", BASE + timedelta(seconds=5), "bypassPermissions", "default"),
        _call("s1", BASE + timedelta(seconds=6)),
    ]
    intervals = mode_intervals(records)
    assert [i.mode for i in intervals] == [
        PermissionMode.DEFAULT,
        PermissionMode.BYPASS_PERMISSIONS,
        PermissionMode.DEFAULT,
    ]
    assert intervals[1].calls == 2


def test_effective_modes_assigns_mode_per_call() -> None:
    records = [
        _call("s1", BASE),
        _transition("s1", BASE + timedelta(seconds=1), "default", "bypassPermissions"),
        bypass_call := _call("s1", BASE + timedelta(seconds=2)),
    ]
    modes = effective_modes(records)
    assert modes[id(bypass_call)] is PermissionMode.BYPASS_PERMISSIONS


def test_missing_mode_is_unknown() -> None:
    record = _call("s1", BASE)
    assert effective_modes([record])[id(record)] is PermissionMode.UNKNOWN


def test_transition_mode_reads_arguments_when_field_absent() -> None:
    from agentwatch.records import AgentRecord, Producer, ProducerKind, StepType, ToolCall

    record = AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="worker"),
        tool=ToolCall(name=MODE_CHANGED_TOOL, arguments={"to": "plan"}),
        outcome=Outcome.OK,
        started_at=BASE,
        harness="claude-code",
        producer=Producer(kind=ProducerKind.INGEST, name="claude-code-otel"),
        step_type=None,
    )
    from agentwatch.permission_mode import transition_mode

    assert transition_mode(record) is PermissionMode.PLAN

    bad = AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="worker"),
        tool=ToolCall(name=MODE_CHANGED_TOOL, arguments={"to": "nonsense"}),
        outcome=Outcome.OK,
        started_at=BASE,
        harness="claude-code",
        producer=Producer(kind=ProducerKind.INGEST, name="claude-code-otel"),
        step_type=None,
    )
    assert transition_mode(bad) is PermissionMode.UNKNOWN


def test_adapter_records_permission_mode() -> None:
    message: dict[str, Any] = {
        "phase": "pre",
        "harness": "claude-code",
        "event": {
            "session_id": "sess-m",
            "tool_name": "Bash",
            "tool_use_id": "call-m",
            "timestamp": "2026-01-02T03:04:05+00:00",
            "permission_mode": "acceptEdits",
        },
    }
    (record,) = claude_code.normalize(message)
    assert record.permission_mode is PermissionMode.ACCEPT_EDITS


def test_otel_mode_change_sets_the_mode_field() -> None:
    payload = {
        "resourceLogs": [
            {
                "resource": {"attributes": []},
                "scopeLogs": [
                    {
                        "scope": {"name": "claude-code"},
                        "logRecords": [
                            {
                                "timeUnixNano": "1767323045000000000",
                                "body": {"stringValue": "claude_code.permission_mode_changed"},
                                "attributes": [
                                    {"key": "session.id", "value": {"stringValue": "s1"}},
                                    {
                                        "key": "to_mode",
                                        "value": {"stringValue": "bypassPermissions"},
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    records, _ = claude_otel.transcode_claude_otel(payload)
    (record,) = records
    assert record.permission_mode is PermissionMode.BYPASS_PERMISSIONS


def test_search_by_mode(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_call("s1", BASE, mode=PermissionMode.DEFAULT))
    bypass = _call("s1", BASE + timedelta(seconds=1), mode=PermissionMode.BYPASS_PERMISSIONS)
    store.append(bypass)

    hits = search(store, permission_mode="bypassPermissions")
    assert [record.span_id for record in hits] == [bypass.span_id]


def test_impact_flags_the_bypass_interval(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_call("s1", BASE, mode=PermissionMode.DEFAULT))
    store.append(_transition("s1", BASE + timedelta(seconds=1), "default", "bypassPermissions"))
    store.append(_call("s1", BASE + timedelta(seconds=2)))
    store.append(_transition("s1", BASE + timedelta(seconds=3), "bypassPermissions", "default"))
    store.append(_call("s1", BASE + timedelta(seconds=4)))

    report = build_impact(store, "s1")
    assert report.bypass_intervals
    assert report.to_dict()["bypass_intervals"]


def test_coverage_counts_unknown_modes(tmp_path: Path) -> None:
    from agentwatch.coverage import build_coverage

    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_call("s1", BASE))
    report = build_coverage(store, transcripts={}, transcripts_present=False)
    assert report.totals["mode_unknown"] >= 1
