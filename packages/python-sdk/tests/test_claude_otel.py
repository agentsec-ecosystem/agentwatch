"""Claude Code native OTel ingest + ``tool_use_id`` join (M29 CCO-1, #444).

Native telemetry is authoritative: exact cost, the permission decision source,
and mode transitions. The join to hook records is by ``tool_use_id`` and any
disagreement is a classified observation, never a silent reconciliation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentwatch import claude_otel
from agentwatch.adapters import claude_code
from agentwatch.cost import build_cost
from agentwatch.records import (
    AuthorizationSource,
    ProducerKind,
    RecordPrivacyMode,
    SecurityEventType,
    StepType,
    validate_record,
)
from agentwatch.redact import PrivacyMode, RedactionConfig
from agentwatch.store import RecordStore

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _log_record(name: str, attrs: dict[str, Any]) -> dict[str, Any]:
    return {
        "timeUnixNano": str(int(AT.timestamp() * 1e9)),
        "attributes": _attrs(attrs),
        "body": {"stringValue": name},
        "severityText": "INFO",
    }


def _payload(
    events: list[dict[str, Any]], *, resource: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "resourceLogs": [
            {
                "resource": {"attributes": _attrs(resource or {})},
                "scopeLogs": [{"scope": {"name": "claude-code"}, "logRecords": events}],
            }
        ]
    }


def _attrs(pairs: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key, value in pairs.items():
        if isinstance(value, bool):
            value = {"boolValue": value}
        elif isinstance(value, int):
            value = {"intValue": value}
        elif isinstance(value, float):
            value = {"doubleValue": value}
        else:
            value = {"stringValue": value}
        out.append({"key": key, "value": value})
    return out


def _transcode(*events: dict[str, Any], resource: dict[str, Any] | None = None):
    return claude_otel.transcode_claude_otel(_payload(list(events), resource=resource))


def _hook(session: str, tool_use_id: str, *, phase: str = "post", **extra: Any) -> Any:
    event: dict[str, Any] = {
        "session_id": session,
        "tool_name": "Bash",
        "tool_use_id": tool_use_id,
        "timestamp": "2026-01-02T03:04:05+00:00",
    }
    event.update(extra)
    message = {"phase": phase, "harness": "claude-code", "event": event}
    return claude_code.normalize(message)[0]


# --- ingest -----------------------------------------------------------------


def test_transcode_tool_decision_classifier() -> None:
    records, problems = _transcode(
        _log_record(
            "claude_code.tool_decision",
            {"session.id": "s1", "tool_use_id": "call-1", "tool_name": "Bash",
             "decision": "allow", "decision_source": "classifier"},
        )
    )

    assert problems == []
    (record,) = records
    assert record.producer is not None
    assert record.producer.kind is ProducerKind.INGEST
    assert record.producer.name == "claude-code-otel"
    assert record.span_id == "call-1"
    assert record.authorization is not None
    assert record.authorization.source is AuthorizationSource.CLASSIFIER
    validate_record(record.to_dict())


def test_transcode_permission_mode_changed_is_a_transition() -> None:
    records, problems = _transcode(
        _log_record(
            "claude_code.permission_mode_changed",
            {"session.id": "s1", "from_mode": "default", "to_mode": "bypassPermissions"},
        )
    )

    assert problems == []
    (record,) = records
    assert record.tool.name == "permission-mode-changed"
    assert record.step_type is None
    assert record.tool.arguments == {"from": "default", "to": "bypassPermissions"}


def test_transcode_api_request_reports_exact_cost(tmp_path: Path) -> None:
    records, _ = _transcode(
        _log_record(
            "claude_code.api_request",
            {"session.id": "s1", "model": "claude-sonnet-4", "input_tokens": 100,
             "output_tokens": 50, "cost_usd": 0.0123},
        )
    )
    (record,) = records
    assert record.tokens == 150
    assert record.cost_usd == 0.0123

    store = RecordStore(tmp_path / "records.jsonl")
    store.append(record)
    report = build_cost(store, by="model")
    assert report.total_cost_source == "exact"
    assert report.total_cost_usd == 0.0123


def test_unmappable_event_is_quarantined_as_a_problem() -> None:
    records, problems = _transcode(_log_record("claude_code.mystery_event", {"session.id": "s1"}))
    assert records == []
    assert problems
    assert "unmappable" in problems[0].reason


def test_default_metadata_only_omits_prompt_content() -> None:
    records, _ = _transcode(
        _log_record(
            "claude_code.user_prompt",
            {"session.id": "s1", "prompt": "do the thing", "prompt.id": "p1"},
        )
    )
    (record,) = records
    assert record.tool.name == "user-prompt"
    assert record.step_type is StepType.REASON
    assert record.tool.arguments is None
    assert record.tool.privacy_mode is RecordPrivacyMode.METADATA_ONLY


def test_prompt_content_captured_only_when_opted_in() -> None:
    cfg = RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_prompts=True)
    records, _ = claude_otel.transcode_claude_otel(
        _payload([
            _log_record(
                "claude_code.user_prompt",
                {"session.id": "s1", "prompt": "do the thing", "prompt.id": "p1"},
            )
        ]),
        redaction=cfg,
    )
    (record,) = records
    assert record.tool.arguments == {"prompt": "do the thing"}
    assert record.tool.privacy_mode is RecordPrivacyMode.TRUNCATED


def test_redaction_runs_on_ingest() -> None:
    records, _ = _transcode(
        _log_record(
            "claude_code.user_prompt",
            {"session.id": "s1", "prompt": "deploy with sk-abcdefgh", "prompt.id": "p1"},
        )
    )
    (record,) = records
    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.SECRET_DETECTED
    assert "sk-abcdefgh" not in str(record.to_dict())


def test_identity_from_resource_attributes() -> None:
    records, _ = _transcode(
        _log_record("claude_code.tool_result", {"session.id": "s1", "tool_use_id": "c1"}),
        resource={"service.name": "builder", "agentwatch.identity": "agent-7"},
    )
    (record,) = records
    assert record.agent.identity == "agent-7"


# --- join -------------------------------------------------------------------


def test_join_by_tool_use_id() -> None:
    hook = _hook("s1", "call-1", phase="post")
    otel, _ = _transcode(
        _log_record("claude_code.tool_result", {"session.id": "s1", "tool_use_id": "call-1"})
    )
    report = claude_otel.join_records([hook, *otel])

    assert len(report.joined) == 1
    assert report.hook_only == ()
    assert report.otel_only == ()
    assert report.summary() == "1 joined, 0 hook-only, 0 otel-only, 0 discrepancies (classified)"


def test_join_classifies_an_outcome_discrepancy() -> None:
    hook = _hook("s1", "call-1", phase="post")
    otel, _ = _transcode(
        _log_record(
            "claude_code.tool_result",
            {"session.id": "s1", "tool_use_id": "call-1", "success": False},
        )
    )
    report = claude_otel.join_records([hook, *otel])

    assert report.joined
    assert [d.field for d in report.discrepancies] == ["outcome"]
    assert "classified" in report.summary()


def test_join_hook_only_and_otel_only() -> None:
    hook = _hook("s1", "hook-1", phase="post")
    otel, _ = _transcode(
        _log_record("claude_code.tool_result", {"session.id": "s1", "tool_use_id": "otel-1"})
    )
    report = claude_otel.join_records([hook, *otel])

    assert report.joined == ()
    assert len(report.hook_only) == 1
    assert len(report.otel_only) == 1
    assert report.summary() == "0 joined, 1 hook-only, 1 otel-only, 0 discrepancies (classified)"


def test_otel_records_are_produced_by_the_otel_producer() -> None:
    otel, _ = _transcode(
        _log_record("claude_code.tool_result", {"session.id": "s1", "tool_use_id": "o1"})
    )
    assert claude_otel.is_otel_record(otel[0])
    assert not claude_otel.is_otel_record(_hook("s1", "h1"))


def test_coverage_reports_native_telemetry_join(tmp_path: Path) -> None:
    from agentwatch.coverage import build_coverage

    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_hook("s1", "call-1", phase="pre"))
    store.append(_hook("s1", "call-1", phase="post"))
    otel, _ = _transcode(
        _log_record("claude_code.tool_result", {"session.id": "s1", "tool_use_id": "call-1"})
    )
    for record in otel:
        store.append(record)

    report = build_coverage(store, transcripts={}, transcripts_present=False)

    assert report.otel_join is not None
    assert report.otel_join.startswith("1 joined")
    assert "hook-only" in report.otel_join
