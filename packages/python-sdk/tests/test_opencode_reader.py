"""OpenCode transcript reader tests (M27 LOG-1 #340).

OpenCode's storage layout and ``ToolPart``/``Session`` shapes are taken from the
MIT-licensed generated SDK types (``packages/sdk/js/src/v2/gen/types.gen.ts``).
These tests build a synthetic storage tree and assert pairing, error/active
states, redaction, idempotent ingest, and that the reader never executes content.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentwatch import opencode_reader
from agentwatch.records import RecordPrivacyMode, SecurityEventType
from agentwatch.redact import PrivacyMode, RedactionConfig

START = 1_766_000_000_000  # epoch ms


def _tree(tmp_path: Path) -> Path:
    storage = tmp_path / "storage"
    info = storage / "session" / "info"
    part = storage / "session" / "part" / "s1" / "m1"
    info.mkdir(parents=True)
    (part).mkdir(parents=True)
    (info / "s1.json").write_text(
        json.dumps(
            {
                "id": "s1",
                "directory": "/home/user/project",
                "version": "1.2.3",
                "model": {"id": "claude-sonnet", "providerID": "anthropic"},
            }
        ),
        encoding="utf-8",
    )
    (part / "p1.json").write_text(
        json.dumps(
            {
                "id": "p1",
                "sessionID": "s1",
                "messageID": "m1",
                "type": "tool",
                "callID": "call_1",
                "tool": "bash",
                "state": {
                    "status": "completed",
                    "input": {"command": "ls -la"},
                    "output": "total 0",
                    "title": "bash",
                    "metadata": {},
                    "time": {"start": START, "end": START + 1000},
                },
            }
        ),
        encoding="utf-8",
    )
    (part / "p2.json").write_text(
        json.dumps(
            {
                "id": "p2",
                "sessionID": "s1",
                "messageID": "m1",
                "type": "tool",
                "callID": "call_2",
                "tool": "read",
                "state": {
                    "status": "error",
                    "input": {"path": "/nope"},
                    "error": "No such file",
                    "time": {"start": START, "end": START + 500},
                },
            }
        ),
        encoding="utf-8",
    )
    (part / "p3.json").write_text(
        json.dumps(
            {
                "id": "p3",
                "sessionID": "s1",
                "messageID": "m1",
                "type": "tool",
                "callID": "call_3",
                "tool": "grep",
                "state": {"status": "running", "input": {"pattern": "x"}, "time": {"start": START}},
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_pairs_tool_parts_and_marks_dangling(tmp_path: Path) -> None:
    read = opencode_reader.read_storage(_tree(tmp_path))

    assert read.sessions == 1
    assert read.dangling == 1
    names = [(r.tool.name, r.step_type.value) for r in read.records if r.step_type]
    assert names == [
        ("bash", "act"),
        ("bash", "observe"),
        ("read", "act"),
        ("read", "observe"),
        ("grep", "act"),
    ]
    assert read.records[0].project == "/home/user/project"
    assert read.records[0].agent.model_version == "claude-sonnet"
    assert read.records[3].outcome.value == "error"


def test_captures_input_and_output_under_full(tmp_path: Path) -> None:
    read = opencode_reader.read_storage(
        _tree(tmp_path), redaction=RedactionConfig(mode=PrivacyMode.FULL)
    )

    act, observe = read.records[0], read.records[1]
    assert act.tool.arguments == {"command": "ls -la"}
    assert act.tool.privacy_mode is RecordPrivacyMode.FULL
    assert observe.tool.response == {"output": "total 0"}


def test_secret_in_input_fires_and_is_not_stored(tmp_path: Path) -> None:
    tree = _tree(tmp_path)
    part = tree / "storage" / "session" / "part" / "s1" / "m1" / "p1.json"
    data = json.loads(part.read_text())
    data["state"]["input"] = {"command": "export TOKEN=sk-abcdefgh"}
    part.write_text(json.dumps(data), encoding="utf-8")

    read = opencode_reader.read_storage(tree, redaction=RedactionConfig(mode=PrivacyMode.FULL))
    act = read.records[0]

    assert act.security_event is not None
    assert act.security_event.type is SecurityEventType.SECRET_DETECTED
    assert "sk-abcdefgh" not in str(act.to_dict())


def test_ingest_is_idempotent(tmp_path: Path) -> None:
    from agentwatch.store import RecordStore

    tree = _tree(tmp_path)
    store = RecordStore(tmp_path / "records.jsonl")

    first = opencode_reader.ingest_storage(tree, store)
    second = opencode_reader.ingest_storage(tree, store)

    assert first.records == 5
    assert second.records == 0
    assert second.duplicates == 5
    assert store.verify().ok


def test_default_storage_dir_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCODE_STORAGE_DIR", "/custom/opencode")
    assert str(opencode_reader.default_storage_dir()) == "/custom/opencode"


def test_reader_never_spawns_a_shell() -> None:
    source = Path(opencode_reader.__file__).read_text(encoding="utf-8")
    assert "subprocess" not in source
    assert "os.system" not in source
    assert "eval(" not in source


def test_cli_ingest_opencode(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from agentwatch.cli.main import main

    tree = _tree(tmp_path)
    store_dir = tmp_path / "store"
    rc = main(
        ["--set", f"store.path={store_dir}", "ingest", str(tree), "--agent", "opencode", "--json"]
    )

    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["records"] == 5
    assert out["sessions"] == 1
    assert out["dangling"] == 1
