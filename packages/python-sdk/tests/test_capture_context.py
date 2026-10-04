"""Approval provenance + context compaction tests (M19 S14/S15, #255/#256)."""

from __future__ import annotations

import json
from pathlib import Path

from agentwatch.adapters import claude_code
from agentwatch.adapters.claude_code import derive_approval
from agentwatch.daemon import Daemon
from agentwatch.install import EVENT_PHASES
from agentwatch.records import Approval, effective_approval
from agentwatch.store import RecordStore

TS = "2026-01-02T03:04:05+00:00"
BASE = {"session_id": "s1", "cwd": "/work", "timestamp": TS}


def _pre(**event: object) -> dict[str, object]:
    return {
        "phase": "pre",
        "harness": "claude-code",
        "event": {**BASE, "tool_name": "Bash", "tool_use_id": "call-1", **event},
    }


# --------------------------------------------------------------------------- S15


def test_compact_records_trigger_and_tokens() -> None:
    message = {
        "phase": "compact",
        "harness": "claude-code",
        "event": {
            **BASE,
            "trigger": "auto",
            "tokens_before": 90000,
            "tokens_after": 30000,
            "summary": "DO NOT STORE THIS PAYLOAD",
        },
    }

    (record,) = claude_code.normalize(message)

    assert record.tool.name == "context-compacted"
    assert record.tool.arguments == {
        "trigger": "auto",
        "tokens_before": 90000,
        "tokens_after": 30000,
    }
    assert "DO NOT STORE THIS PAYLOAD" not in json.dumps(record.to_dict())


def test_compact_missing_tokens_are_omitted_and_trigger_unknown() -> None:
    message = {"phase": "compact", "harness": "claude-code", "event": {**BASE, "trigger": "weird"}}

    (record,) = claude_code.normalize(message)

    assert record.tool.arguments == {"trigger": "unknown"}


def test_repeated_compactions_are_not_coalesced() -> None:
    message = {"phase": "compact", "harness": "claude-code", "event": {**BASE, "trigger": "manual"}}
    records = [
        claude_code.normalize(message)[0],
        claude_code.normalize(message)[0],
    ]
    assert len(records) == 2


def test_precompact_and_notification_phases_registered() -> None:
    assert EVENT_PHASES["PreCompact"] == "compact"
    assert EVENT_PHASES["Notification"] == "notification"


# --------------------------------------------------------------------------- S14


def test_approval_denied() -> None:
    message = {"phase": "denied", "harness": "claude-code", "event": {**BASE, "tool_name": "Bash"}}
    (record,) = claude_code.normalize(message)
    assert record.approval is Approval.DENIED
    assert effective_approval(record) is Approval.DENIED


def test_approval_user_from_pending_permission() -> None:
    (record,) = claude_code.normalize(_pre(), pending_permission=True)
    assert record.approval is Approval.USER


def test_approval_auto_from_allowlist() -> None:
    (record,) = claude_code.normalize(
        _pre(permission_decision="allow", permission_source="allowlist")
    )
    assert record.approval is Approval.AUTO


def test_approval_not_required() -> None:
    (record,) = claude_code.normalize(_pre(permission_required=False))
    assert record.approval is Approval.NOT_REQUIRED


def test_approval_unknown_is_not_written() -> None:
    (record,) = claude_code.normalize(_pre())
    assert record.approval is None
    assert effective_approval(record) is Approval.UNKNOWN


def test_approval_explicit_field_wins() -> None:
    (record,) = claude_code.normalize(_pre(approval="user"))
    assert record.approval is Approval.USER


def test_derive_approval_never_guesses_ambiguous_allow() -> None:
    event = {"permission_decision": "allow"}
    assert derive_approval("pre", event) is Approval.UNKNOWN


def test_notification_phase_is_metadata_only() -> None:
    message = {
        "phase": "notification",
        "harness": "claude-code",
        "event": {**BASE, "tool_name": "Bash", "tool_use_id": "call-9"},
    }

    (record,) = claude_code.normalize(message)

    assert record.tool.name == "permission-prompt"
    assert record.tool.arguments == {"tool": "Bash"}


def test_daemon_correlates_prompt_with_next_pre(tmp_path: Path) -> None:
    daemon = Daemon(
        socket_path=str(tmp_path / "d.sock"),
        records_path=tmp_path / "records.jsonl",
    )
    prompt = {
        "phase": "notification",
        "harness": "claude-code",
        "event": {**BASE, "tool_name": "Bash", "tool_use_id": "call-7"},
    }
    pre = {
        "phase": "pre",
        "harness": "claude-code",
        "event": {**BASE, "tool_name": "Bash", "tool_use_id": "call-7"},
    }

    daemon.handle_message(prompt)
    (record,) = daemon.handle_message(pre)

    assert record.approval is Approval.USER


def test_daemon_unprompted_pre_is_unknown(tmp_path: Path) -> None:
    daemon = Daemon(
        socket_path=str(tmp_path / "d.sock"),
        records_path=tmp_path / "records.jsonl",
    )
    pre = {
        "phase": "pre",
        "harness": "claude-code",
        "event": {**BASE, "tool_name": "Bash", "tool_use_id": "call-8"},
    }

    (record,) = daemon.handle_message(pre)

    assert record.approval is None


def test_search_filters_by_approval(tmp_path: Path) -> None:
    from agentwatch.query import search

    store = RecordStore(tmp_path / "records.jsonl")
    daemon = Daemon(socket_path=str(tmp_path / "d.sock"), store=store)
    daemon.handle_message(
        {"phase": "denied", "harness": "claude-code", "event": {**BASE, "tool_name": "Bash"}}
    )
    daemon.handle_message(
        {"phase": "pre", "harness": "claude-code", "event": {**BASE, "tool_name": "Read"}}
    )

    denied = search(store, approval="denied")

    assert len(denied) == 1
    assert denied[0].tool.name == "Bash"
    assert search(store, approval="unknown")[0].tool.name == "Read"
