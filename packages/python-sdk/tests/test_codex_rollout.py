"""Codex CLI rollout reader tests (M27 COD-1 #339).

The format is documented and verified from the ``openai/codex`` source
(``docs/codex-format.md`` in kvsankar/agent-history). These tests replay the
documented record types, ``.jsonl.zst``, dedup (F2), and the dangling-session
``crashed`` end-state (S33), and prove the reader never executes foreign content.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from agentwatch import codex_rollout
from agentwatch.records import RecordPrivacyMode, SecurityEventType
from agentwatch.redact import PrivacyMode, RedactionConfig

SESSION = "rollout-2025-12-08T00-37-46-abc123"


def _zstd_open(path: Path, mode: str) -> Any:
    for name in ("compression.zstd", "zstandard"):
        try:
            module: Any = importlib.import_module(name)
        except ImportError:
            continue
        return module.open(path, mode, encoding="utf-8")
    pytest.skip("no zstd backend available")


def _lines() -> list[dict[str, object]]:
    return [
        {
            "timestamp": "2025-12-08T00:37:46.102Z",
            "type": "session_meta",
            "payload": {"id": SESSION, "cwd": "/home/user/project", "cli_version": "0.65.0"},
        },
        {
            "timestamp": "2025-12-08T00:38:00.000Z",
            "type": "turn_context",
            "payload": {"model": "o4-mini"},
        },
        {
            "timestamp": "2025-12-08T00:39:59.538Z",
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "shell",
                "arguments": '{"command": "ls -la"}',
                "call_id": "call_abc123",
            },
        },
        {
            "timestamp": "2025-12-08T00:40:00.000Z",
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "call_id": "call_abc123",
                "output": "total 0",
            },
        },
        {
            "timestamp": "2025-12-08T00:40:03.000Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {"total_token_usage": {"total_tokens": 124866}},
            },
        },
        {"timestamp": "2025-12-08T00:40:04.000Z", "type": "ghost_snapshot", "payload": {}},
    ]


def _write(tmp_path: Path, lines: list[dict[str, object]]) -> Path:
    path = tmp_path / f"{SESSION}.jsonl"
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return path


def test_pairs_function_call_with_output(tmp_path: Path) -> None:
    read = codex_rollout.read_rollout(_write(tmp_path, _lines()))

    assert read.session_id == SESSION
    assert read.dangling is False
    assert read.tokens == 124866
    call, output = read.records[0], read.records[1]
    assert call.tool.name == "shell"
    assert call.step_type is not None and call.step_type.value == "act"
    assert call.span_id == "call_abc123"
    assert output.step_type is not None and output.step_type.value == "observe"
    assert output.span_id == "call_abc123"
    assert output.project == "/home/user/project"
    assert output.agent.model_version == "o4-mini"
    assert output.agent.version == "0.65.0"


def test_captures_arguments_under_full(tmp_path: Path) -> None:
    read = codex_rollout.read_rollout(
        _write(tmp_path, _lines()), redaction=RedactionConfig(mode=PrivacyMode.FULL)
    )

    call = read.records[0]
    assert call.tool.arguments == {"command": "ls -la"}
    assert call.tool.privacy_mode is RecordPrivacyMode.FULL


def test_dangling_session_is_inferred_crashed(tmp_path: Path) -> None:
    lines = _lines()[:3]  # a function_call with no output
    read = codex_rollout.read_rollout(_write(tmp_path, lines))

    assert read.dangling is True
    assert read.records[-1].outcome.value == "error"
    assert read.records[-1].tool.name == "shell"


def test_unknown_types_are_skipped_not_fatal(tmp_path: Path) -> None:
    lines: list[dict[str, object]] = [
        *_lines(),
        {"timestamp": "2025-12-08T00:41:00.000Z", "type": "future_thing", "payload": {}},
    ]
    read = codex_rollout.read_rollout(_write(tmp_path, lines))

    assert read.skipped >= 2  # ghost_snapshot + future_thing
    assert read.session_id == SESSION


def test_duplicate_lines_are_deduped(tmp_path: Path) -> None:
    lines = _lines()
    lines.insert(3, lines[2])  # duplicate the function_call line
    read = codex_rollout.read_rollout(_write(tmp_path, lines))

    assert read.duplicates == 1
    assert [r.tool.name for r in read.records].count("shell") == 2  # one ACT + one OBSERVE


def test_jsonl_zst_is_read(tmp_path: Path) -> None:
    path = tmp_path / f"{SESSION}.jsonl.zst"
    with _zstd_open(path, "wt") as handle:
        for line in _lines():
            handle.write(json.dumps(line) + "\n")

    read = codex_rollout.read_rollout(path)

    assert read.session_id == SESSION
    assert read.records[0].tool.name == "shell"


def test_secret_in_arguments_fires_and_is_not_stored(tmp_path: Path) -> None:
    lines = _lines()
    lines[2]["payload"] = {
        "type": "function_call",
        "name": "shell",
        "arguments": '{"command": "export TOKEN=sk-abcdefgh"}',
        "call_id": "call_abc123",
    }
    read = codex_rollout.read_rollout(
        _write(tmp_path, lines), redaction=RedactionConfig(mode=PrivacyMode.FULL)
    )

    call = read.records[0]
    assert call.security_event is not None
    assert call.security_event.type is SecurityEventType.SECRET_DETECTED
    assert "sk-abcdefgh" not in str(call.to_dict())


def test_reader_never_spawns_a_shell() -> None:
    # Untrusted-data rule (ADR-0024): no subprocess/eval on a reader path.
    source = Path(codex_rollout.__file__).read_text(encoding="utf-8")
    assert "subprocess" not in source
    assert "os.system" not in source
    assert "eval(" not in source


def test_ingest_rollouts_is_idempotent(tmp_path: Path) -> None:
    from agentwatch.store import RecordStore

    path = _write(tmp_path, _lines())
    store = RecordStore(tmp_path / "records.jsonl")

    first = codex_rollout.ingest_rollouts([path], store)
    second = codex_rollout.ingest_rollouts([path], store)

    assert first.records == 2
    assert second.records == 0
    assert second.duplicates == 2
    assert len(store.records()) == 2
    assert store.verify().ok
