"""Redaction-receipt tests (M15 S32, #237).

Receipts name rule ids and field paths, never values; they are derived at read
time; and ``redact --preview`` leaves the store byte-identical.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.receipts import record_receipt, redact_preview, session_receipts
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)
from agentwatch.redact import PrivacyMode, RedactionConfig
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(**overrides: object) -> AgentRecord:
    base: dict[str, object] = {
        "session_id": "s1",
        "agent": AgentIdentity(identity="agent"),
        "tool": ToolCall(name="Bash", arguments={"cmd": "ls"}),
        "outcome": Outcome.OK,
        "started_at": START,
    }
    base.update(overrides)
    return AgentRecord(**base)  # type: ignore[arg-type]


def test_masked_secret_is_a_dropped_field_with_a_secret_rule() -> None:
    record = _record(tool=ToolCall(name="Bash", arguments={"token": "<REDACTED:api-key>"}))

    receipt = record_receipt(record)

    assert "tool.arguments.token" in receipt.dropped
    assert "secrets:api-key" in receipt.rules
    assert "tool.arguments.cmd" not in receipt.kept  # only the token key exists


def test_metadata_only_drops_the_argument_field() -> None:
    record = _record(
        tool=ToolCall(name="Bash", privacy_mode=RecordPrivacyMode.METADATA_ONLY),
    )

    receipt = record_receipt(record)

    assert "tool.arguments" in receipt.dropped
    assert "privacy-mode:metadata-only" in receipt.rules


def test_both_mode_and_secret_rules_are_reported_independently() -> None:
    record = _record(
        tool=ToolCall(
            name="Bash",
            arguments={"token": "<REDACTED:api-key>"},
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        )
    )

    receipt = record_receipt(record)

    assert "privacy-mode:metadata-only" in receipt.rules
    assert "secrets:api-key" in receipt.rules
    assert "tool.response" in receipt.dropped


def test_truncation_rule_names_the_cap() -> None:
    record = _record(tool=ToolCall(name="Bash", arguments={"cmd": "x" * 500 + "[...]"}))

    receipt = record_receipt(record)

    assert any(rule.startswith("truncation:") for rule in receipt.rules)
    assert "tool.arguments.cmd" in receipt.kept


def test_non_string_fields_are_kept_by_path_only() -> None:
    record = _record(tool=ToolCall(name="Bash", arguments={"count": 3, "nested": {"ok": True}}))

    receipt = record_receipt(record)

    assert "tool.arguments.count" in receipt.kept
    assert "tool.arguments.nested.ok" in receipt.kept
    assert receipt.dropped == ()


def test_clean_record_has_an_empty_receipt() -> None:
    receipt = record_receipt(_record())

    assert receipt.dropped == ()
    assert receipt.rules == ()
    assert "tool.arguments.cmd" in receipt.kept


def test_session_receipts_cover_every_record(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    store.append(_record(tool=ToolCall(name="Read", arguments={"token": "<REDACTED:api-key>"})))

    receipts = session_receipts(store, "s1")

    assert len(receipts) == 2
    assert receipts[0].seq == 0
    assert receipts[1].seq == 1


def test_session_receipts_skip_tombstoned_records(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    store.append(_record(tool=ToolCall(name="Read", arguments={"cmd": "cat"})))
    store.purge_session("s1")

    receipts = session_receipts(store, "s1")

    # Tombstoned records carry no payload and yield no receipt; only the
    # metadata-only purge marker remains in the chain.
    assert len(receipts) == 1
    assert all("tool.arguments.cmd" not in receipt.kept for receipt in receipts)


def test_list_fields_are_walked_by_index() -> None:
    record = _record(
        tool=ToolCall(
            name="Bash",
            arguments={"steps": ["ok", "<REDACTED:api-key>"]},
        )
    )

    receipt = record_receipt(record)

    assert "tool.arguments.steps[0]" in receipt.kept
    assert "tool.arguments.steps[1]" in receipt.dropped
    assert "secrets:api-key" in receipt.rules


def test_preview_masks_and_applies_mode() -> None:
    preview = redact_preview(
        '{"cmd": "sk-LEAK-abcdefgh"}',
        RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_tool_args=True),
    )

    assert "sk-LEAK-abcdefgh" not in preview.after
    assert "<REDACTED:api-key>" in preview.after
    assert "secrets:api-key" in preview.rules


def test_preview_metadata_only_reports_the_mode_rule() -> None:
    preview = redact_preview("hello", RedactionConfig(mode=PrivacyMode.METADATA_ONLY))

    assert preview.after == "null"
    assert "privacy-mode:metadata-only" in preview.rules


def test_preview_walks_a_json_array() -> None:
    preview = redact_preview(
        '["ok", "sk-LEAK-abcdefgh", 3]',
        RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_tool_args=True),
    )

    assert "sk-LEAK-abcdefgh" not in preview.after
    assert "<REDACTED:api-key>" in preview.after
    assert "secrets:api-key" in preview.rules


def test_cli_replay_receipts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    store.append(
        _record(tool=ToolCall(name="Bash", arguments={"token": "<REDACTED:api-key>"}))
    )

    rc = main(["--set", f"store.path={store_dir}", "replay", "s1", "--receipts", "--json"])

    assert rc == 0
    out = capsys.readouterr().out
    assert '"receipt"' in out
    assert "secrets:api-key" in out


def test_cli_redact_preview_stores_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store_file = store_dir / "records.jsonl"
    store = RecordStore(store_file)
    store.append(_record())
    before = store_file.read_text(encoding="utf-8")

    rc = main(
        ["--set", f"store.path={store_dir}", "redact", "--preview", '{"cmd": "sk-LEAK-abcdefgh"}']
    )

    assert rc == 0
    out = capsys.readouterr().out
    after_line = next(line for line in out.splitlines() if line.startswith("after:"))
    assert "sk-LEAK-abcdefgh" not in after_line
    assert "secrets:api-key" in out
    assert store_file.read_text(encoding="utf-8") == before


def test_cli_redact_preview_creates_no_store(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()

    rc = main(["--set", f"store.path={store_dir}", "redact", "--preview", "plain sample"])

    assert rc == 0
    assert not (store_dir / "records.jsonl").exists()
