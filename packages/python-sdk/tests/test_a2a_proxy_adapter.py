"""A2A proxy adapter tests (M29 A2A-1 #364, PRD 45, ADR-0025).

The adapter maps framed A2A (agent-to-agent) JSON-RPC traffic to agentwatch
records: task lifecycle, messages, artifacts, and agent-card exchanges. It
mirrors the MCP proxy adapter: declared gaps and unknown phases are rejected
explicitly, never dropped silently (PRD 17).
"""

from __future__ import annotations

from typing import Any

import pytest

from agentwatch import conformance
from agentwatch.adapters import a2a_proxy
from agentwatch.records import RecordPrivacyMode, SecurityEventType
from agentwatch.redact import PrivacyMode, RedactionConfig


def _request(**event_overrides: Any) -> dict[str, Any]:
    event: dict[str, Any] = {
        "agent": "remote-scheduler",
        "session_id": "s-1",
        "direction": "request",
        "rpc": {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": "m-1",
                    "taskId": "t-1",
                    "contextId": "ctx-1",
                    "role": "user",
                    "parts": [{"kind": "text", "text": "schedule it"}],
                }
            },
        },
        "timestamp": "2026-01-02T03:04:05+00:00",
        "cwd": "/repo",
    }
    event.update(event_overrides)
    return {"phase": "a2a", "harness": "a2a-proxy", "event": event}


def test_message_send_request_becomes_an_intent_record() -> None:
    record = a2a_proxy.normalize(_request())[0].to_dict()

    assert record["session_id"] == "s-1"
    assert record["agent"] == {"identity": "remote-scheduler"}
    assert record["tool"] == {
        "name": "message/send",
        "server": "remote-scheduler",
        "arguments": {"message_id": "m-1", "task_id": "t-1", "context_id": "ctx-1"},
        "privacy_mode": "metadata-only",
    }
    assert record["outcome"] == "ok"
    assert record["started_at"] == "2026-01-02T03:04:05+00:00"
    assert record["trace_id"] == "s-1"
    assert record["span_id"] == "a2a:remote-scheduler:7"
    assert record["harness"] == "a2a-proxy"
    assert record["project"] == "/repo"
    assert record["producer"] == {"kind": "proxy", "name": "a2a-proxy"}
    assert record["step_type"] == "act"


def test_task_response_becomes_an_outcome_record_and_artifacts() -> None:
    message = _request(
        direction="response",
        tool_name="message/send",
        rpc={
            "jsonrpc": "2.0",
            "id": 7,
            "result": {
                "kind": "task",
                "id": "t-1",
                "status": {"state": "completed"},
                "artifacts": [{"artifactId": "a-1", "name": "schedule"}],
            },
        },
        timestamp="2026-01-02T03:04:06+00:00",
    )
    records = a2a_proxy.normalize(message)

    outcome = records[0].to_dict()
    assert outcome["tool"] == {
        "name": "message/send",
        "server": "remote-scheduler",
        "arguments": {"task_id": "t-1", "state": "completed"},
        "privacy_mode": "metadata-only",
    }
    assert outcome["step_type"] == "observe"
    assert outcome["outcome"] == "ok"
    assert outcome["span_id"] == "a2a:remote-scheduler:7"
    assert outcome["ended_at"] == "2026-01-02T03:04:06+00:00"

    artifact = records[1].to_dict()
    assert artifact["tool"] == {
        "name": "a2a/artifact",
        "server": "remote-scheduler",
        "arguments": {"artifact_id": "a-1", "name": "schedule"},
        "privacy_mode": "metadata-only",
    }
    assert artifact["step_type"] == "observe"
    assert artifact["span_id"] == "a2a:remote-scheduler:7-artifact-0"


def test_error_response_is_an_error_outcome() -> None:
    message = _request(
        direction="response",
        tool_name="message/send",
        rpc={"jsonrpc": "2.0", "id": 7, "error": {"code": -32000, "message": "boom"}},
    )
    assert a2a_proxy.normalize(message)[0].outcome.value == "error"


def test_tasks_get_request_keeps_the_task_id() -> None:
    message = _request(
        rpc={
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tasks/get",
            "params": {"id": "t-9"},
        }
    )
    record = a2a_proxy.normalize(message)[0]
    assert record.tool.name == "tasks/get"
    assert record.tool.arguments == {"task_id": "t-9"}


def test_tasks_cancel_request_is_recorded() -> None:
    message = _request(
        rpc={"jsonrpc": "2.0", "id": 9, "method": "tasks/cancel", "params": {"id": "t-9"}}
    )
    assert a2a_proxy.normalize(message)[0].tool.name == "tasks/cancel"


def test_agent_card_exchange_is_recorded_with_a_digest() -> None:
    card = {
        "name": "Remote Scheduler",
        "url": "https://scheduler.acme.example/a2a",
        "version": "1.0.0",
        "provider": {"organization": "Acme", "url": "https://acme.example"},
    }
    message = {
        "phase": "a2a",
        "harness": "a2a-proxy",
        "event": {
            "agent": "remote-scheduler",
            "session_id": "s-1",
            "direction": "card",
            "card": card,
            "source": "server",
            "timestamp": "2026-01-02T03:04:05+00:00",
            "cwd": "/repo",
        },
    }
    record = a2a_proxy.normalize(message)[0]

    assert record.tool.name == "a2a/agent-card"
    assert record.tool.server == "remote-scheduler"
    assert record.agent.identity == "remote-scheduler"
    assert record.agent.name == "Remote Scheduler"
    assert record.tool.arguments is not None
    assert record.tool.arguments["agent"] == "Remote Scheduler"
    assert record.tool.arguments["org"] == "Acme"
    assert len(record.tool.arguments["card_digest"]) == 64
    assert record.step_type.value == "observe"
    assert record.host == "scheduler.acme.example"


@pytest.mark.parametrize(
    "method",
    [
        "tasks/resubscribe",
        "tasks/pushNotificationConfig/set",
        "agent/getAuthenticatedExtendedCard",
    ],
)
def test_declared_gap_methods_are_rejected(method: str) -> None:
    message = _request(rpc={"jsonrpc": "2.0", "id": 1, "method": method, "params": {}})
    with pytest.raises(a2a_proxy.A2aProxyAdapterError):
        a2a_proxy.normalize(message)


@pytest.mark.parametrize(
    "phase", [*a2a_proxy.DOCUMENTED_GAPS, "__unsupported-conformance-phase__"]
)
def test_unsupported_phase_is_rejected(phase: str) -> None:
    with pytest.raises(a2a_proxy.A2aProxyAdapterError):
        a2a_proxy.normalize({"phase": phase, "event": {}})


def test_bad_direction_is_rejected() -> None:
    with pytest.raises(a2a_proxy.A2aProxyAdapterError):
        a2a_proxy.normalize(_request(direction="sideways"))


def test_missing_agent_is_rejected() -> None:
    message = _request()
    del message["event"]["agent"]
    with pytest.raises(a2a_proxy.A2aProxyAdapterError):
        a2a_proxy.normalize(message)


def test_response_without_tool_name_is_rejected() -> None:
    message = _request(direction="response", rpc={"jsonrpc": "2.0", "id": 7, "result": {}})
    with pytest.raises(a2a_proxy.A2aProxyAdapterError):
        a2a_proxy.normalize(message)


def test_secret_in_message_fires_secret_detected_and_is_not_stored() -> None:
    message = _request(
        rpc={
            "jsonrpc": "2.0",
            "id": 7,
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": "m-1",
                    "parts": [{"kind": "text", "text": "export TOKEN=sk-abcdefgh"}],
                }
            },
        }
    )
    record = a2a_proxy.normalize(message)[0]
    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.SECRET_DETECTED
    assert "sk-abcdefgh" not in str(record.to_dict())


def test_content_is_captured_only_when_redaction_allows() -> None:
    message = _request()
    record = a2a_proxy.normalize(
        message, redaction=RedactionConfig(mode=PrivacyMode.TRUNCATED)
    )[0]
    assert record.tool.privacy_mode is RecordPrivacyMode.TRUNCATED
    assert record.tool.arguments is not None
    assert record.tool.arguments["role"] == "user"


def test_passes_the_shared_conformance_runner() -> None:
    import conformance_registry

    conformance.assert_conforms(conformance_registry.a2a_proxy_spec())