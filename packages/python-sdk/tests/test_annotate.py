"""Operator-note tests (M15 S20, #236).

An annotation is a metadata-only, append-only record in the chain: redacted before
storage, filterable by tag, valid even on a purged session, and never an edit.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.annotate import (
    NOTE_MAX_LENGTH,
    OPERATOR_NOTE_TOOL,
    AnnotateError,
    annotate_session,
    operator_notes,
    tagged_sessions,
)
from agentwatch.cli.main import main
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(session: str, tool: str = "Bash") -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=tool),
        outcome=Outcome.OK,
        started_at=START,
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s1", "Bash"))
    return store


def _notes(store: RecordStore) -> list[AgentRecord]:
    return [r for r in store.records() if r.tool.name == OPERATOR_NOTE_TOOL]


def test_annotate_appends_a_note_record(tmp_path: Path) -> None:
    store = _store(tmp_path)

    report = annotate_session(store, "s1", "looks like exfiltration", tag="reviewed")

    assert report.tag == "reviewed"
    assert report.session_purged is False
    notes = _notes(store)
    assert len(notes) == 1
    assert notes[0].tool.arguments == {"note": "looks like exfiltration", "tag": "reviewed"}
    assert store.verify().ok


def test_empty_note_is_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(AnnotateError):
        annotate_session(store, "s1", "   ")


def test_empty_tag_is_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(AnnotateError):
        annotate_session(store, "s1", "note", tag="  ")


def test_unknown_session_is_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(AnnotateError):
        annotate_session(store, "nope", "note")


def test_secret_in_note_is_masked_before_storage(tmp_path: Path) -> None:
    store = _store(tmp_path)

    report = annotate_session(store, "s1", "key is sk-LEAK-abcdefgh maybe")

    assert report.masked_kinds == ("api-key",)
    arguments = _notes(store)[0].tool.arguments
    assert arguments is not None
    note = arguments["note"]
    assert "sk-LEAK-abcdefgh" not in note
    assert "<REDACTED:api-key>" in note
    assert "sk-LEAK-abcdefgh" not in store.path.read_text(encoding="utf-8")


def test_note_is_length_capped(tmp_path: Path) -> None:
    store = _store(tmp_path)
    annotate_session(store, "s1", "x" * (NOTE_MAX_LENGTH + 100))
    arguments = _notes(store)[0].tool.arguments
    assert arguments is not None
    assert len(arguments["note"]) == NOTE_MAX_LENGTH


def test_note_on_purged_session_records_context(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.purge_session("s1")

    report = annotate_session(store, "s1", "post-purge finding", tag="reviewed")

    assert report.session_purged is True
    arguments = _notes(store)[0].tool.arguments
    assert arguments is not None
    assert arguments["session_purged"] is True
    assert arguments["context"] == "session purged"
    assert store.verify().ok


def test_operator_notes_and_tags(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.append(_record("s2", "Read"))
    annotate_session(store, "s1", "a", tag="reviewed")
    annotate_session(store, "s2", "b", tag="escalated")
    annotate_session(store, "s2", "c")

    assert len(operator_notes(store)) == 3
    assert len(operator_notes(store, session_id="s2")) == 2
    assert tagged_sessions(store, "reviewed") == {"s1"}
    assert tagged_sessions(store, "escalated") == {"s2"}
    assert tagged_sessions(store, "missing") == set()


def test_notes_are_append_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    annotate_session(store, "s1", "first")
    annotate_session(store, "s1", "correction")

    notes = operator_notes(store)
    assert [n.note for n in notes] == ["first", "correction"]


def test_cli_annotate_then_sessions_tag_filter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)

    rc = main(
        ["--set", f"store.path={store_dir}", "annotate", "s1", "--note", "hi", "--tag", "reviewed"]
    )
    assert rc == 0
    assert "noted session s1" in capsys.readouterr().out

    rc = main(["--set", f"store.path={store_dir}", "sessions", "--tag", "reviewed"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "s1" in out

    rc = main(["--set", f"store.path={store_dir}", "sessions", "--tag", "missing"])
    assert rc == 0
    assert "s1" not in capsys.readouterr().out


def test_cli_annotate_unknown_session_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)

    rc = main(["--set", f"store.path={store_dir}", "annotate", "nope", "--note", "hi"])

    assert rc != 0
    assert "no records" in capsys.readouterr().err
