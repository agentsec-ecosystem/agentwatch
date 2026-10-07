"""ACS Guardian audit-trail ingest (M29 ACS-1, #367).

Guardian decisions (allow/deny/modify/ask/defer) are our security events with AAT
``record_phase: pre_execution``. The spec is young, so the revision is pinned and
drift-surfaced, unknown frames are quarantined, and agentwatch **records only** —
it never executes a Guardian decision (monitor-only).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from agentwatch import acs
from agentwatch.records import (
    Outcome,
    ProducerKind,
    RecordPhase,
    RecordPrivacyMode,
    SecurityEventType,
    validate_record,
)
from agentwatch.redact import PrivacyMode, RedactionConfig
from agentwatch.store import RecordStore

AT = datetime(2026, 4, 30, 10, 30, 0, tzinfo=timezone.utc)
REQ_ID = "550e8400-e29b-41d4-a716-446655440000"


def _request(
    method: str = "steps/toolCallRequest",
    *,
    request_id: str = REQ_ID,
    session: str = "s1",
    tool: str = "email.send",
    acs_version: str = acs.ACS_VERSION,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "method": method,
        "id": "req-001",
        "params": {
            "acs_version": acs_version,
            "request_id": request_id,
            "timestamp": "2026-04-30T10:30:00Z",
            "tenant_id": "acme-corp",
            "metadata": {"agent_id": "cursor-agent-01", "session_id": session, "turn_id": "t-7"},
            "payload": payload if payload is not None else {"tool": {"name": tool}},
        },
    }


def _response(
    *,
    request_id: str = REQ_ID,
    decision: str = "allow",
    acs_version: str = acs.ACS_VERSION,
    reasoning: str | None = None,
    policies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": "final",
        "acs_version": acs_version,
        "request_id": request_id,
        "decision": decision,
    }
    if reasoning is not None:
        result["reasoning"] = reasoning
    if policies is not None:
        result["policy_references"] = policies
    return {"jsonrpc": "2.0", "id": "req-001", "result": result}


def _trail(*frames: dict[str, Any]) -> dict[str, Any]:
    return {"acs_version": acs.ACS_VERSION, "messages": list(frames)}


# --- decision mapping --------------------------------------------------------


def test_deny_decision_maps_to_denied_pre_execution() -> None:
    records, problems = acs.transcode_acs(
        _trail(
            _request(),
            _response(
                decision="deny",
                reasoning="FIDES P-T denies.",
                policies=[{"policy_id": "acme-baseline", "rule_id": "no-untrusted"}],
            ),
        )
    )

    assert problems == []
    (record,) = records
    assert record.outcome is Outcome.DENIED
    assert record.record_phase is RecordPhase.PRE_EXECUTION
    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.DENIED
    assert record.security_event.policy_id == "acme-baseline"
    assert record.tool.name == "email.send"
    validate_record(record.to_dict())


def test_modify_decision_maps_to_policy_fired() -> None:
    records, problems = acs.transcode_acs(
        _trail(
            _request(),
            _response(decision="modify", reasoning="Limited query to prevent data exposure."),
        )
    )

    assert problems == []
    (record,) = records
    assert record.record_phase is RecordPhase.PRE_EXECUTION
    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.POLICY_FIRED


def test_allow_decision_is_recorded_without_a_security_event() -> None:
    records, problems = acs.transcode_acs(_trail(_request(), _response(decision="allow")))

    assert problems == []
    (record,) = records
    assert record.outcome is Outcome.OK
    assert record.record_phase is RecordPhase.PRE_EXECUTION
    assert record.security_event is None


def test_record_is_labeled_acs_and_monitor_only() -> None:
    records, _ = acs.transcode_acs(_trail(_request(), _response(decision="deny")))
    (record,) = records
    assert record.harness == "acs"
    assert record.producer is not None
    assert record.producer.kind is ProducerKind.INGEST
    assert record.producer.name == "acs"
    assert record.environment is not None
    assert record.environment["source"] == "acs"
    assert record.environment["decision"] == "deny"
    assert acs.is_acs_record(record)
    assert acs.MONITOR_ONLY is True
    assert acs.EMIT_SIDE_BUILT is False


# --- foreign-input rejection (reject-never-invent) ---------------------------


def test_unknown_revision_is_quarantined() -> None:
    records, problems = acs.transcode_acs(
        _trail(_request(acs_version="9.9.9"), _response(decision="allow", acs_version="9.9.9"))
    )
    assert records == []
    assert problems
    assert "unsupported ACS revision" in problems[0].reason


def test_unknown_method_is_quarantined() -> None:
    records, problems = acs.transcode_acs(
        _trail(_request(method="steps/mysteryHook"), _response(decision="allow"))
    )
    assert records == []
    assert problems
    assert "unmappable ACS method" in problems[0].reason


def test_wrapped_protocol_method_maps() -> None:
    records, problems = acs.transcode_acs(
        _trail(
            _request(method="protocols/MCP/tools/call", tool="mcp__server__tool"),
            _response(decision="deny"),
        )
    )
    assert problems == []
    (record,) = records
    assert record.tool.name == "mcp__server__tool"


def test_missing_revision_is_quarantined() -> None:
    request = _request()
    del request["params"]["acs_version"]
    records, problems = acs.transcode_acs(_trail(request, _response(decision="allow")))
    assert records == []
    assert "unsupported ACS revision" in problems[0].reason


def test_bare_message_list_is_accepted() -> None:
    records, problems = acs.transcode_acs([_request(), _response(decision="allow")])
    assert problems == []
    assert [r.tool.name for r in records] == ["email.send"]


def test_allow_with_a_secret_is_a_secret_detected_event() -> None:
    records, _ = acs.transcode_acs(
        _trail(
            _request(payload={"tool": {"name": "http.fetch"}}),
            _response(decision="allow", reasoning="token sk-abcdefghij"),
        )
    )
    (record,) = records
    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.SECRET_DETECTED


def test_unknown_decision_is_quarantined() -> None:
    records, problems = acs.transcode_acs(_trail(_request(), _response(decision="escalate")))
    assert records == []
    assert problems
    assert "unmappable ACS decision" in problems[0].reason


def test_decision_frame_without_request_is_quarantined() -> None:
    records, problems = acs.transcode_acs(_trail(_response(decision="deny")))
    assert records == []
    assert problems
    assert "without a matching request" in problems[0].reason


def test_non_json_payload_is_a_problem_not_a_crash() -> None:
    records, problems = acs.transcode_acs("not json")
    assert records == []
    assert "invalid JSON" in problems[0].reason


# --- version pin + drift (AAT-5 pattern) -------------------------------------


def test_check_acs_drift_reports_a_dropped_field() -> None:
    report = acs.check_acs_drift({"revision": "0.1.0", "fields": ["acs_version", "request_id"]})
    assert report.pinned == acs.ACS_VERSION
    assert report.drifted
    assert "decision" in report.missing


def test_check_acs_drift_reports_a_revision_bump() -> None:
    report = acs.check_acs_drift({"revision": "0.2.0", "fields": list(acs.ACS_SPEC_FIELDS)})
    assert report.drifted
    assert report.upstream == "0.2.0"


# --- privacy ----------------------------------------------------------------


def test_secrets_are_masked_before_storage() -> None:
    cfg = RedactionConfig(mode=PrivacyMode.FULL, capture_tool_args=True)
    records, _ = acs.transcode_acs(
        _trail(
            _request(
                payload={
                    "tool": {"name": "http.fetch"},
                    "arguments": {"token": "sk-abcdefghij"},
                }
            ),
            _response(decision="deny", reasoning="leaked sk-abcdefghij"),
        ),
        redaction=cfg,
    )
    (record,) = records
    assert record.tool.privacy_mode is RecordPrivacyMode.FULL
    assert "sk-abcdefghij" not in str(record.to_dict())
    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.DENIED


# --- store / conformance / CLI ----------------------------------------------


def test_run_ingest_appends_acs_decisions(tmp_path: Path) -> None:
    from agentwatch.ingest import run_ingest

    store = RecordStore(tmp_path / "records.jsonl")
    source = tmp_path / "trail.json"
    source.write_text(
        json.dumps(_trail(_request(), _response(decision="deny"))), encoding="utf-8"
    )
    stats = run_ingest([source], store, fmt="acs")
    assert stats.records == 1
    assert [r.security_event.type for r in store.records() if r.security_event] == [
        SecurityEventType.DENIED
    ]


def test_conformance_pack_conforms() -> None:
    import sdk_conformance_registry  # noqa: F401

    from agentwatch import conformance

    report = conformance.run_sdk(sdk_conformance_registry.acs_spec())
    assert report.ok, report.summary()
    assert "acs" in {spec.name for spec in conformance.registered_sdks()}


def test_cli_ingests_an_acs_trail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from agentwatch.cli.main import main

    source = tmp_path / "trail.json"
    source.write_text(
        json.dumps(_trail(_request(), _response(decision="deny"))), encoding="utf-8"
    )
    store_dir = tmp_path / "store"
    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "ingest",
            str(source),
            "--format",
            "acs",
            "--json",
        ]
    )

    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["records"] == 1


# --- branch coverage ---------------------------------------------------------


def test_version_line() -> None:
    assert acs.acs_version_line() == f"ACS {acs.ACS_VERSION}"


def test_drift_report_to_dict() -> None:
    report = acs.check_acs_drift({"revision": "0.1.0", "fields": list(acs.ACS_SPEC_FIELDS)})
    assert report.to_dict() == {
        "pinned_revision": acs.ACS_VERSION,
        "upstream_revision": "0.1.0",
        "missing": [],
        "extra": [],
        "drifted": False,
    }


def test_frame_without_any_id_is_quarantined() -> None:
    request = {
        "jsonrpc": "2.0",
        "method": "steps/toolCallRequest",
        "params": {"acs_version": acs.ACS_VERSION},
    }
    response = {
        "jsonrpc": "2.0",
        "result": {"acs_version": acs.ACS_VERSION, "decision": "deny"},
    }
    records, problems = acs.transcode_acs([request, response])
    assert records == []
    assert problems


def test_single_frame_and_non_message_payload() -> None:
    records, problems = acs.transcode_acs(_request())
    assert records == []
    assert problems == []
    _records, problems = acs.transcode_acs(123)
    assert "not a message" in problems[0].reason


def test_pairs_by_request_id_without_top_level_id() -> None:
    request = _request()
    request.pop("id")
    response = _response(decision="deny")
    response.pop("id")

    records, problems = acs.transcode_acs([request, response])

    assert problems == []
    assert records[0].security_event is not None


def test_timestamp_fallbacks() -> None:
    request = _request()
    request["params"]["timestamp"] = 1767323045
    records, _ = acs.transcode_acs(_trail(request, _response(decision="allow")))
    assert records[0].started_at.year == 2026

    broken = _request()
    broken["params"]["timestamp"] = "not-a-date"
    records, problems = acs.transcode_acs(_trail(broken, _response(decision="allow")))
    assert problems == []
    assert records


def test_capability_and_reason_codes_are_captured() -> None:
    request = _request(payload={"tool": {"name": "x"}, "capability": "network.egress"})
    response = _response(decision="deny", reasoning=None)
    response["result"]["reason_codes"] = ["fides_p_t_failed"]

    records, _ = acs.transcode_acs(_trail(request, response))

    (record,) = records
    assert record.environment is not None
    assert record.environment["capability"] == "network.egress"
    assert record.security_event is not None
    assert record.security_event.evidence["reason_codes"] == ["fides_p_t_failed"]


def test_unknown_namespace_method_is_quarantined() -> None:
    records, problems = acs.transcode_acs(
        _trail(_request(method="handshake/hello"), _response(decision="allow"))
    )
    assert records == []
    assert "unmappable ACS method" in problems[0].reason


def test_request_without_params_is_quarantined() -> None:
    request = {"jsonrpc": "2.0", "method": "steps/toolCallRequest", "id": "r1"}
    response = {
        "jsonrpc": "2.0",
        "id": "r1",
        "result": {"acs_version": acs.ACS_VERSION, "decision": "deny"},
    }

    records, problems = acs.transcode_acs([request, response])

    assert records == []
    assert "no params" in problems[0].reason


def test_response_revision_mismatch_is_quarantined() -> None:
    records, problems = acs.transcode_acs(
        _trail(_request(), _response(decision="allow", acs_version="9.9.9"))
    )
    assert records == []
    assert "unsupported ACS revision" in problems[0].reason


def test_metadata_only_capture_omits_arguments() -> None:
    records, _ = acs.transcode_acs(
        _trail(
            _request(payload={"tool": {"name": "x"}, "arguments": {"a": "b"}}),
            _response(decision="allow"),
        )
    )
    (record,) = records
    assert record.tool.arguments is None


def test_list_arguments_are_redacted() -> None:
    cfg = RedactionConfig(mode=PrivacyMode.FULL, capture_tool_args=True)
    records, _ = acs.transcode_acs(
        _trail(
            _request(
                payload={
                    "tool": {"name": "x"},
                    "arguments": {"n": 5, "vals": ["sk-abcdefghij"]},
                }
            ),
            _response(decision="allow"),
        ),
        redaction=cfg,
    )
    (record,) = records
    assert "sk-abcdefghij" not in str(record.to_dict())
