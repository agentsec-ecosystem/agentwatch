"""Tests for transcript import (M8 addition H1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentwatch.cli import main
from agentwatch.importer import import_transcripts, iter_records, resolve_paths
from agentwatch.redact import redaction_config_from_mode
from agentwatch.store import RecordStore

_FIXTURE = Path(__file__).parent / "fixtures" / "claude-code" / "transcript_sample.jsonl"


def test_iter_records_pairs_calls_and_keeps_unmatched() -> None:
    records = list(iter_records([_FIXTURE]))

    assert [record.tool.name for record in records] == ["Bash", "Read", "Write"]
    assert records[0].outcome.value == "ok"
    assert records[1].outcome.value == "error"
    assert all(record.session_id == "sess-t" for record in records)


def test_metadata_only_import_captures_no_content(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")

    stats = import_transcripts([_FIXTURE], store)

    assert stats.records == 3
    assert all(record.tool.arguments is None for record in store.records())


def test_truncated_import_masks_secrets(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    redaction = redaction_config_from_mode("truncated")

    import_transcripts([_FIXTURE], store, redaction=redaction)

    write = next(record for record in store.records() if record.tool.name == "Write")
    assert write.tool.arguments is not None
    assert write.tool.arguments["content"] == "<REDACTED:api-key>"


def test_resolve_paths_expands_directory(tmp_path: Path) -> None:
    nested = tmp_path / "projects" / "p"
    nested.mkdir(parents=True)
    (nested / "a.jsonl").write_text("{}\n", encoding="utf-8")

    assert resolve_paths(tmp_path) == [nested / "a.jsonl"]
    assert resolve_paths(_FIXTURE) == [_FIXTURE]


def test_cli_import_reports_and_stores(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(["--set", f"store.path={tmp_path}", "import", str(_FIXTURE)]) == 0
    )
    out = capsys.readouterr().out
    assert "imported 3 records" in out

    store = RecordStore(tmp_path / "records.jsonl")
    assert len(store.records()) == 3


def test_cli_import_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(["--set", f"store.path={tmp_path}", "import", str(_FIXTURE), "--json"]) == 0
    )
    out = capsys.readouterr().out
    assert '"records": 3' in out
