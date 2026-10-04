"""MCP proxy adapter tests (M10 N1 #83).

The adapter maps a framed MCP JSON-RPC ``tools/call`` request/response to
agentwatch records. Declared gaps and unknown phases are rejected explicitly,
never dropped silently (PRD 17).
"""

from __future__ import annotations

from typing import Any

import pytest

from agentwatch.adapters import mcp_proxy
from agentwatch.records import RecordPrivacyMode, SecurityEventType
from agentwatch.redact import PrivacyMode, RedactionConfig


def _request(**event_overrides: Any) -> dict[str, Any]:
    event: dict[str, Any] = {
        "server": "github",
        "session_id": "s-1",
        "direction": "request",
        "rpc": {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "issue_get", "arguments": {"number": 3}},
        },
        "timestamp": "2026-01-02T03:04:05+00:00",
        "cwd": "/repo",
    }
    event.update(event_overrides)
    return {"phase": "mcp", "harness": "mcp-proxy", "event": event}


def test_request_becomes_an_intent_record() -> None:
    records = mcp_proxy.normalize(_request())
    assert len(records) == 1
    assert records[0].to_dict() == {
        "schema_version": "0.1.0",
        "session_id": "s-1",
        "agent": {"identity": "unknown"},
        "tool": {"name": "issue_get", "server": "github"},
        "outcome": "ok",
        "started_at": "2026-01-02T03:04:05+00:00",
        "trace_id": "s-1",
        "span_id": "mcp:github:7",
        "harness": "mcp-proxy",
        "project": "/repo",
        "producer": {"kind": "proxy", "name": "mcp-proxy"},
        "step_type": "act",
    }


def test_response_becomes_an_outcome_record() -> None:
    message = _request(
        direction="response",
        tool_name="issue_get",
        rpc={"jsonrpc": "2.0", "id": 7, "result": {"ok": True}},
        timestamp="2026-01-02T03:04:06+00:00",
    )
    record = mcp_proxy.normalize(message)[0].to_dict()
    assert record["step_type"] == "observe"
    assert record["outcome"] == "ok"
    assert record["span_id"] == "mcp:github:7"
    assert record["tool"] == {"name": "issue_get", "server": "github"}
    assert record["ended_at"] == "2026-01-02T03:04:06+00:00"


def test_error_response_is_an_error_outcome() -> None:
    message = _request(
        direction="response",
        tool_name="issue_get",
        rpc={"jsonrpc": "2.0", "id": 7, "error": {"code": -32000, "message": "boom"}},
    )
    assert mcp_proxy.normalize(message)[0].outcome.value == "error"


def test_response_without_tool_name_is_rejected() -> None:
    message = _request(direction="response", rpc={"jsonrpc": "2.0", "id": 7, "result": {}})
    with pytest.raises(mcp_proxy.McpProxyAdapterError):
        mcp_proxy.normalize(message)


@pytest.mark.parametrize("phase", [*mcp_proxy.DOCUMENTED_GAPS, "__unsupported-conformance-phase__"])
def test_unsupported_phase_is_rejected(phase: str) -> None:
    with pytest.raises(mcp_proxy.McpProxyAdapterError):
        mcp_proxy.normalize({"phase": phase, "event": {}})


def test_non_tools_call_method_is_rejected() -> None:
    message = _request(rpc={"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {}})
    with pytest.raises(mcp_proxy.McpProxyAdapterError):
        mcp_proxy.normalize(message)


def test_secret_in_arguments_fires_secret_detected_and_is_not_stored() -> None:
    message = _request(
        rpc={
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "issue_get", "arguments": {"cmd": "export TOKEN=sk-abcdefgh"}},
        }
    )
    record = mcp_proxy.normalize(message)[0]
    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.SECRET_DETECTED
    assert "sk-abcdefgh" not in str(record.to_dict())


def test_missing_id_means_no_span_id() -> None:
    message = _request(rpc={"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "x"}})
    assert mcp_proxy.normalize(message)[0].span_id is None


def test_malformed_event_is_rejected() -> None:
    with pytest.raises(mcp_proxy.McpProxyAdapterError):
        mcp_proxy.normalize({"phase": "mcp", "event": "not-an-object"})


def test_non_mapping_message_is_rejected() -> None:
    with pytest.raises(mcp_proxy.McpProxyAdapterError):
        mcp_proxy.normalize("not-a-mapping")  # type: ignore[arg-type]


def test_missing_server_is_rejected() -> None:
    with pytest.raises(mcp_proxy.McpProxyAdapterError):
        mcp_proxy.normalize(_request(server=""))


def test_missing_rpc_is_rejected() -> None:
    with pytest.raises(mcp_proxy.McpProxyAdapterError):
        mcp_proxy.normalize(_request(rpc="nope"))


def test_invalid_direction_is_rejected() -> None:
    with pytest.raises(mcp_proxy.McpProxyAdapterError):
        mcp_proxy.normalize(_request(direction="sideways"))


def test_missing_params_is_rejected() -> None:
    rpc = {"jsonrpc": "2.0", "id": 1, "method": "tools/call"}
    with pytest.raises(mcp_proxy.McpProxyAdapterError):
        mcp_proxy.normalize(_request(rpc=rpc))


def test_missing_tool_name_in_request_is_rejected() -> None:
    rpc = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {}}
    with pytest.raises(mcp_proxy.McpProxyAdapterError):
        mcp_proxy.normalize(_request(rpc=rpc))


def test_missing_timestamp_defaults_to_now() -> None:
    message = _request()
    del message["event"]["timestamp"]
    assert mcp_proxy.normalize(message)[0].started_at.tzinfo is not None


def test_invalid_timestamp_is_rejected() -> None:
    with pytest.raises(mcp_proxy.McpProxyAdapterError):
        mcp_proxy.normalize(_request(timestamp="not-a-timestamp"))


def test_boolean_id_has_no_span_id() -> None:
    rpc = {"jsonrpc": "2.0", "id": True, "method": "tools/call", "params": {"name": "x"}}
    assert mcp_proxy.normalize(_request(rpc=rpc))[0].span_id is None


def test_trace_id_comes_from_the_event() -> None:
    assert mcp_proxy.normalize(_request(trace_id="t-9"))[0].trace_id == "t-9"


def test_call_id_distinguishes_reused_rpc_ids() -> None:
    first = mcp_proxy.normalize(_request(call_id="c1"))[0]
    second = mcp_proxy.normalize(_request(call_id="c2"))[0]
    assert first.span_id == "mcp:github:c1"
    assert second.span_id == "mcp:github:c2"


def test_full_capture_records_redacted_arguments() -> None:
    cfg = RedactionConfig(mode=PrivacyMode.FULL)
    record = mcp_proxy.normalize(_request(), redaction=cfg)[0]
    assert record.tool.arguments == {"number": 3}
    assert record.tool.privacy_mode is RecordPrivacyMode.FULL


def test_full_capture_records_an_error_response() -> None:
    cfg = RedactionConfig(mode=PrivacyMode.FULL)
    message = _request(
        direction="response",
        tool_name="issue_get",
        rpc={"jsonrpc": "2.0", "id": 7, "error": {"code": 1, "message": "boom"}},
    )
    record = mcp_proxy.normalize(message, redaction=cfg)[0]
    assert record.tool.response == {"code": 1, "message": "boom"}
    assert record.tool.privacy_mode is RecordPrivacyMode.FULL
    assert record.outcome.value == "error"
