"""Claude Code native OTel ingest + ``tool_use_id`` join (M29 CCO-1, #444).

Native telemetry is authoritative: exact cost, the permission decision source,
and mode transitions. The join to hook records is by ``tool_use_id`` and any
disagreement is a classified observation, never a silent reconciliation.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentwatch import claude_otel
from agentwatch.adapters import claude_code
from agentwatch.cost import build_cost
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Authorization,
    AuthorizationEvidence,
    AuthorizationSource,
    Outcome,
    Producer,
    ProducerKind,
    RecordPrivacyMode,
    SecurityEventType,
    StepType,
    ToolCall,
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


def _transcode(
    *events: dict[str, Any], resource: dict[str, Any] | None = None
) -> tuple[list[Any], list[Any]]:
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


# --- robustness: metric/trace decoding, malformed input, join edge cases ------


def _metric(name: str, kind: str, points: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "resourceMetrics": [
            {
                "resource": {"attributes": _attrs({"service.name": "cc"})},
                "scopeMetrics": [{"scope": {"name": "claude-code"}, "metrics": [
                    {"name": name, kind: {"dataPoints": points}},
                ]}],
            }
        ]
    }


def test_transcode_token_and_cost_metrics() -> None:
    payload = {
        "resourceMetrics": [
            {
                "resource": {"attributes": []},
                "scopeMetrics": [
                    {
                        "metrics": [
                            {"name": "claude_code.token.usage",
                             "sum": {"dataPoints": [{"asInt": 150, "attributes": []}]}},
                            {"name": "claude_code.cost.usage",
                             "gauge": {"data_points": [{"asDouble": 0.5, "attributes": []}]}},
                            {"name": "claude_code.other",
                             "sum": {"dataPoints": [{"asInt": 9, "attributes": []}]}},
                        ]
                    }
                ],
            }
        ]
    }
    records, problems = claude_otel.transcode_claude_otel(payload)

    assert problems == []
    assert [record.tokens for record in records] == [150, None]
    assert records[1].cost_usd == 0.5


def test_transcode_bad_metric_shapes_are_skipped() -> None:
    payload = {
        "resourceMetrics": [
            "not-a-mapping",
            {
                "scopeMetrics": [
                    "not-a-mapping",
                    {"metrics": "not-a-list"},
                    {"metrics": [
                        "not-a-mapping",
                        {"name": 7},
                        {"name": "claude_code.token.usage", "sum": "not-a-mapping"},
                        {"name": "claude_code.token.usage",
                         "sum": {"dataPoints": "not-a-list"}},
                        {"name": "claude_code.token.usage",
                         "sum": {"dataPoints": ["not-a-mapping"]}},
                    ]},
                ]
            },
        ]
    }
    records, problems = claude_otel.transcode_claude_otel(payload)
    assert records == []
    assert problems == []


def test_transcode_bad_log_shapes_are_skipped() -> None:
    payload = {
        "resourceLogs": [
            "not-a-mapping",
            {"scopeLogs": "not-a-list"},
            {"scopeLogs": [
                "not-a-mapping",
                {"logRecords": "not-a-list"},
                {"logRecords": ["not-a-mapping"]},
            ]},
        ]
    }
    records, problems = claude_otel.transcode_claude_otel(payload)
    assert records == []
    assert problems == []


def test_transcode_non_mapping_payload_is_empty() -> None:
    assert claude_otel.transcode_claude_otel(["nope"]) == ([], [])
    assert claude_otel.transcode_claude_otel({"unrelated": True}) == ([], [])
    assert claude_otel.transcode_claude_otel(
        {"resourceMetrics": [{"scopeMetrics": "not-a-list"}]}
    ) == ([], [])


def test_event_name_from_plain_string_body() -> None:
    payload = {
        "resourceLogs": [
            {
                "resource": {"attributes": []},
                "scopeLogs": [
                    {"logRecords": [{"body": "claude_code.tool_result",
                                     "attributes": _attrs({"tool_use_id": "c1"})}]}
                ],
            }
        ]
    }
    records, problems = claude_otel.transcode_claude_otel(payload)
    assert [record.tool.name for record in records] == ["tool-result"]
    assert problems == []


def test_invalid_token_counts_are_none() -> None:
    records, _ = _transcode(
        _log_record(
            "claude_code.api_request",
            {"session.id": "s1", "input_tokens": "abc", "output_tokens": "def"},
        )
    )
    assert records[0].tokens is None


def test_event_name_from_body_mapping_and_attribute() -> None:
    payload = {
        "resourceLogs": [
            {
                "resource": {"attributes": []},
                "scopeLogs": [
                    {
                        "logRecords": [
                            {"body": {"kvlistValue": {"values": []}}},
                            {"attributes": _attrs({"event.name": "claude_code.tool_result",
                                                   "tool_use_id": "x1"})},
                        ]
                    }
                ],
            }
        ]
    }
    records, problems = claude_otel.transcode_claude_otel(payload)
    # the first body is not a usable name; the second is a tool_result.
    assert [record.tool.name for record in records] == ["tool-result"]
    assert len(problems) == 1


def test_tool_result_error_duration_and_tokens() -> None:
    records, _ = _transcode(
        _log_record(
            "claude_code.tool_result",
            {"session.id": "s1", "tool_use_id": "c1", "success": False,
             "duration_ms": 12.5, "total_tokens": 300, "status": "error"},
        )
    )
    (record,) = records
    assert record.outcome is Outcome.ERROR
    assert record.duration_ms == 12.5
    assert record.tokens == 300


def test_token_value_fallback_and_invalid_cost() -> None:
    payload = _metric("claude_code.token.usage", "sum", [{"asDouble": 42.0}])
    payload["resourceMetrics"][0]["scopeMetrics"][0]["metrics"][0]["sum"]["dataPoints"][0][
        "attributes"
    ] = _attrs({})
    records, _ = claude_otel.transcode_claude_otel(payload)
    assert records[0].tokens == 42

    records, _ = _transcode(
        _log_record(
            "claude_code.api_request",
            {"session.id": "s1", "model": "m", "cost_usd": "not-a-number"},
        )
    )
    assert records[0].cost_usd is None


def test_api_request_records_model() -> None:
    records, _ = _transcode(
        _log_record(
            "claude_code.api_request",
            {"session.id": "s1", "model": "claude-sonnet-4", "cost_usd": 0.1},
        )
    )
    assert records[0].agent.model_version == "claude-sonnet-4"


def test_mcp_server_connection_maps_server_and_transport() -> None:
    records, _ = _transcode(
        _log_record(
            "claude_code.mcp_server_connection",
            {"session.id": "s1", "server_name": "github", "transport": "stdio"},
        )
    )
    (record,) = records
    assert record.tool.name == "mcp-server-connection"
    assert record.tool.arguments == {"server": "github", "transport": "stdio"}


def test_tool_decision_deny_without_source() -> None:
    records, _ = _transcode(
        _log_record(
            "claude_code.tool_decision",
            {"session.id": "s1", "tool_use_id": "c1", "decision": "deny"},
        )
    )
    (record,) = records
    assert record.outcome is Outcome.DENIED
    assert record.authorization is not None
    assert record.authorization.source is AuthorizationSource.DENIED


def test_tool_decision_unknown_source_stays_absent() -> None:
    records, _ = _transcode(
        _log_record(
            "claude_code.tool_decision",
            {"session.id": "s1", "tool_use_id": "c1", "decision_source": "mystery"},
        )
    )
    assert records[0].authorization is None


def test_user_prompt_hashed_capture_and_no_secret_event() -> None:
    cfg = RedactionConfig(mode=PrivacyMode.HASHED, capture_prompts=True, hash_salt="s")
    records, _ = claude_otel.transcode_claude_otel(
        _payload([
            _log_record(
                "claude_code.user_prompt",
                {"session.id": "s1", "prompt": "hello", "prompt.id": "p1"},
            )
        ]),
        redaction=cfg,
    )
    (record,) = records
    assert record.tool.privacy_mode is RecordPrivacyMode.HASHED
    assert record.security_event is None


def test_transcode_trace_span() -> None:
    payload = {
        "spans": [
            {
                "name": "claude_code.tool_result",
                "traceId": "t1",
                "spanId": "s1",
                "startTimeUnixNano": "1767323045000000000",
                "attributes": [{"key": "event.name", "value": {"stringValue":
                    "claude_code.tool_result"}},
                    {"key": "tool_use_id", "value": {"stringValue": "c1"}}],
            },
            {"name": "something_else", "spanId": "s2"},
        ]
    }
    records, problems = claude_otel.transcode_claude_otel(payload)
    assert [record.tool.name for record in records] == ["tool-result"]
    assert problems


def _hook_with_cost(span: str, cost: float, auth: Authorization) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="worker"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=AT,
        harness="claude-code",
        producer=Producer(kind=ProducerKind.HOOK, name="claude-code"),
        span_id=span,
        ended_at=AT,
        step_type=StepType.OBSERVE,
        cost_usd=cost,
        authorization=auth,
    )


def test_join_classifies_cost_and_authorization_discrepancies() -> None:
    hook = _hook_with_cost(
        "c1",
        0.01,
        Authorization(source=AuthorizationSource.CLASSIFIER,
                      evidence=AuthorizationEvidence.HARNESS_NATIVE),
    )
    otel, _ = _transcode(
        _log_record("claude_code.tool_result",
                    {"session.id": "s1", "tool_use_id": "c1", "cost_usd": 0.02})
    )
    report = claude_otel.join_records([hook, *otel])
    assert {d.field for d in report.discrepancies} == {"cost"}
    assert report.to_dict()["joined"] == 1


def test_join_authorization_discrepancy() -> None:
    hook = _hook_with_cost(
        "c1",
        0.0,
        Authorization(source=AuthorizationSource.CLASSIFIER,
                      evidence=AuthorizationEvidence.HARNESS_NATIVE),
    )
    otel, _ = _transcode(
        _log_record("claude_code.tool_decision",
                    {"session.id": "s1", "tool_use_id": "c1",
                     "decision_source": "config"})
    )
    report = claude_otel.join_records([hook, *otel])
    assert [d.field for d in report.discrepancies] == ["authorization"]


def test_join_handles_spanless_records() -> None:
    hook = _hook_with_cost("", 0.0, Authorization(
        source=AuthorizationSource.RULE, evidence=AuthorizationEvidence.INFERRED))
    hook = replace(hook, span_id=None)
    otel, _ = _transcode(_log_record("claude_code.tool_result", {"session.id": "s1"}))
    report = claude_otel.join_records([hook, *otel])
    assert len(report.hook_only) == 1
    assert len(report.otel_only) == 1


def test_join_representative_falls_back_to_first_hook() -> None:
    first = _hook("s1", "call-1", phase="pre")
    second = _hook("s1", "call-1", phase="pre")
    otel, _ = _transcode(
        _log_record("claude_code.tool_result", {"session.id": "s1", "tool_use_id": "call-1"})
    )
    report = claude_otel.join_records([first, second, *otel])
    assert len(report.joined) == 1
    assert report.discrepancies == ()


def test_otel_join_summary_none_without_native() -> None:
    assert claude_otel.otel_join_summary([_hook("s1", "h1")]) is None


def test_ingest_transcode_claude_otel_format(tmp_path: Path) -> None:
    import json

    from agentwatch.ingest import run_ingest, transcode

    payload = _payload([
        _log_record(
            "claude_code.tool_result",
            {"session.id": "s1", "tool_use_id": "c1", "total_tokens": 10},
        )
    ])
    path = tmp_path / "native.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    records, problems = transcode(path, fmt="claude-otel")
    assert problems == []
    assert records[0].producer.name == "claude-code-otel"

    store = RecordStore(tmp_path / "records.jsonl")
    stats = run_ingest([path], store, fmt="claude-otel")
    assert stats.records == 1


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
