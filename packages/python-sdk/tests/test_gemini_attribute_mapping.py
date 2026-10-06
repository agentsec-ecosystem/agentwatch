"""Gemini native-telemetry attribute mapping tests (M27 GEM-2 #342).

Gemini CLI's built-in OTel telemetry carries attributes we would otherwise infer:
``active_approval_mode`` → approval provenance (S14), ``user.email`` → on-behalf-of
principal (hashed by default, IDN-1), and ``installation.id``/``session.id`` →
identity / session correlation.
"""

from __future__ import annotations

from typing import Any

from agentwatch.adapters import gemini_cli
from agentwatch.records import Approval


def _tool_call(**overrides: Any) -> dict[str, Any]:
    event: dict[str, Any] = {
        "session_id": "sess-g",
        "tool": "run_shell",
        "timestamp": "2026-01-02T03:04:05+00:00",
    }
    event.update(overrides)
    return {"phase": "tool_call", "harness": "gemini-cli", "event": event}


def test_active_approval_mode_auto_maps_to_auto() -> None:
    record = gemini_cli.normalize(_tool_call(active_approval_mode="auto"))[0]
    assert record.approval is Approval.AUTO


def test_active_approval_mode_on_request_maps_to_user() -> None:
    record = gemini_cli.normalize(_tool_call(active_approval_mode="on-request"))[0]
    assert record.approval is Approval.USER


def test_active_approval_mode_never_maps_to_denied() -> None:
    record = gemini_cli.normalize(_tool_call(active_approval_mode="never"))[0]
    assert record.approval is Approval.DENIED


def test_unknown_approval_mode_is_honest_unknown() -> None:
    record = gemini_cli.normalize(_tool_call(active_approval_mode="surprise"))[0]
    assert record.approval is Approval.UNKNOWN


def test_absent_approval_mode_is_none() -> None:
    assert gemini_cli.normalize(_tool_call())[0].approval is None


def test_user_email_becomes_a_hashed_principal() -> None:
    record = gemini_cli.normalize(_tool_call(**{"user.email": "human@corp.example"}))[0]
    assert record.agent.principal is not None
    assert record.agent.principal != "human@corp.example"
    assert "human@corp.example" not in str(record.to_dict())


def test_installation_and_session_ids_map_to_identity() -> None:
    record = gemini_cli.normalize(
        _tool_call(**{"installation.id": "install-77", "session.id": "otel-sess-9"})
    )[0]
    assert record.agent.identity == "install-77"
    assert record.session_id == "otel-sess-9"
