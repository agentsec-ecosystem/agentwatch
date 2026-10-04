"""Quarantine operator-tooling tests (M16 S27, #241).

The dead-letter queue gets handles: list (no payload), inspect (redacted by
default; ``--raw`` gated and audited), requeue through the adapter, and an
explicit clear. A requeue that still fails stays quarantined with its new reason.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.adapters import claude_code
from agentwatch.cli.main import main
from agentwatch.quarantine import (
    QuarantineError,
    QuarantineLog,
    clear_entries,
    inspect_entry,
    list_entries,
    requeue_entries,
    select_entries,
)
from agentwatch.store import RecordStore
from agentwatch.store_access import store_accesses

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
SECRET = "sk-LEAK-abcdefgh"

FRAME = json.dumps(
    {
        "phase": "pre",
        "harness": "claude-code",
        "event": {
            "session_id": "s1",
            "tool_name": "Bash",
            "tool_use_id": "c1",
            "timestamp": "2026-01-02T03:04:05+00:00",
        },
    }
)


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith("AGENTWATCH_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path / "store"))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return tmp_path


def _log(tmp_path: Path) -> QuarantineLog:
    return QuarantineLog(tmp_path / "quarantine.jsonl")


def _store(tmp_path: Path) -> RecordStore:
    return RecordStore(tmp_path / "records.jsonl")


def test_list_summaries_have_no_payload(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.add(FRAME, reason="normalize-error")
    log.add(f"a secret {SECRET}", reason="malformed-line")

    entries = list_entries(log)

    assert len(entries) == 2
    assert all(set(entry.summary()) == {"id", "reason", "at"} for entry in entries)
    assert SECRET not in json.dumps([entry.summary() for entry in entries])


def test_inspect_redacts_by_default_without_an_access_record(tmp_path: Path) -> None:
    log = _log(tmp_path)
    store = _store(tmp_path)
    log.add(f"leaked {SECRET} here", reason="malformed-line")
    entry_id = log.records()[0].id

    report = inspect_entry(log, store, entry_id)

    assert report.raw is False
    assert SECRET not in report.payload
    assert "<REDACTED:api-key>" in report.payload
    assert store_accesses(store) == []


def test_inspect_raw_is_recorded_as_store_access(tmp_path: Path) -> None:
    log = _log(tmp_path)
    store = _store(tmp_path)
    log.add(f"leaked {SECRET} here", reason="malformed-line")
    entry_id = log.records()[0].id

    report = inspect_entry(log, store, entry_id, raw=True)

    assert report.raw is True
    assert SECRET in report.payload
    accesses = store_accesses(store)
    assert [access.command for access in accesses] == ["quarantine-inspect"]
    assert store.verify().ok


def test_inspect_missing_id_raises(tmp_path: Path) -> None:
    with pytest.raises(QuarantineError):
        inspect_entry(_log(tmp_path), _store(tmp_path), "nope")


def test_requeue_after_a_fix_moves_the_entry_into_the_store(tmp_path: Path) -> None:
    log = _log(tmp_path)
    store = _store(tmp_path)
    log.add(FRAME, reason="normalize-error")

    report = requeue_entries(log, store, normalizer=lambda message: claude_code.normalize(message))

    assert report.requeued == 1
    assert report.records == 1
    assert report.remaining == 0
    records = store.records()
    assert len(records) == 1
    assert records[0].session_id == "s1"
    assert log.records() == []


def test_requeue_still_failing_stays_with_new_reason(tmp_path: Path) -> None:
    log = _log(tmp_path)
    store = _store(tmp_path)
    log.add("not a frame", reason="malformed-line")

    report = requeue_entries(
        log, store, normalizer=lambda message: claude_code.normalize(message), all_entries=True
    )

    assert report.requeued == 0
    assert report.still_failing == 1
    assert report.remaining == 1
    remaining = log.records()
    assert len(remaining) == 1
    assert remaining[0].reason.startswith("requeue-error")


def test_requeue_unknown_id_raises(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.add(FRAME, reason="normalize-error")
    with pytest.raises(QuarantineError):
        select_entries(log, ids=["missing"])


def test_clear_requires_yes_when_not_empty(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.add(FRAME, reason="normalize-error")

    with pytest.raises(QuarantineError):
        clear_entries(log, yes=False)

    assert clear_entries(log, yes=True) == 1
    assert log.records() == []


# -- CLI ---------------------------------------------------------------------


def _seed(store_dir: Path) -> QuarantineLog:
    store_dir.mkdir(parents=True, exist_ok=True)
    log = QuarantineLog(store_dir / "quarantine.jsonl")
    log.add(FRAME, reason="normalize-error")
    log.add(f"secret {SECRET}", reason="malformed-line")
    return log


def test_cli_list_inspect_requeue_clear(isolated: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = isolated / "store"
    log = _seed(store_dir)
    target = next(e for e in log.records() if "secret" in e.raw)

    rc = main(["--set", f"store.path={store_dir}", "quarantine", "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert target.id in out
    assert SECRET not in out

    rc = main(["--set", f"store.path={store_dir}", "quarantine", "inspect", target.id])
    assert rc == 0
    out = capsys.readouterr().out
    assert SECRET not in out
    assert "<REDACTED:api-key>" in out

    frame_id = next(e for e in log.records() if "phase" in e.raw).id
    rc = main(["--set", f"store.path={store_dir}", "quarantine", "requeue", frame_id])
    assert rc == 0
    assert "requeued 1" in capsys.readouterr().out
    store = RecordStore(store_dir / "records.jsonl")
    assert any(record.session_id == "s1" for record in store.records())

    rc = main(["--set", f"store.path={store_dir}", "quarantine", "clear"])
    assert rc != 0
    assert "clear" in capsys.readouterr().err

    rc = main(["--set", f"store.path={store_dir}", "quarantine", "clear", "--yes"])
    assert rc == 0
    assert "cleared" in capsys.readouterr().out
    assert log.records() == []


def test_cli_inspect_raw_records_access(isolated: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = isolated / "store"
    log = _seed(store_dir)
    target = next(e for e in log.records() if "secret" in e.raw)

    rc = main(["--set", f"store.path={store_dir}", "quarantine", "inspect", target.id, "--raw"])

    assert rc == 0
    assert SECRET in capsys.readouterr().out
    store = RecordStore(store_dir / "records.jsonl")
    assert [access.command for access in store_accesses(store)] == ["quarantine-inspect"]


def test_cli_inspect_missing_id_fails(isolated: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = isolated / "store"
    store_dir.mkdir()
    rc = main(["--set", f"store.path={store_dir}", "quarantine", "inspect", "nope"])
    assert rc != 0
    assert "no quarantine entry" in capsys.readouterr().err


def test_records_have_stable_ids(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.add(FRAME, reason="normalize-error")
    first = log.records()[0].id
    assert log.get(first) is not None
    assert _log(tmp_path).records()[0].id == first


def test_requeue_valid_json_non_object_stays(tmp_path: Path) -> None:
    log = _log(tmp_path)
    store = _store(tmp_path)
    log.add("123", reason="malformed-line")

    report = requeue_entries(
        log, store, normalizer=lambda message: claude_code.normalize(message), all_entries=True
    )

    assert report.still_failing == 1
    assert "not a JSON object" in log.records()[0].reason


def test_requeue_normalizer_empty_or_raising_stays(tmp_path: Path) -> None:
    log = _log(tmp_path)
    store = _store(tmp_path)
    log.add(FRAME, reason="normalize-error")

    empty = requeue_entries(log, store, normalizer=lambda message: [], all_entries=True)
    assert empty.still_failing == 1
    assert "no records" in log.records()[0].reason

    def boom(message: object) -> list[object]:
        raise ValueError("still broken")

    raised = requeue_entries(log, store, normalizer=boom, all_entries=True)  # type: ignore[arg-type]
    assert raised.still_failing == 1
    assert "still broken" in log.records()[0].reason


def test_entries_skip_bad_lines_and_derive_legacy_ids(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.path.write_text(
        "\n5\n{not json\n"
        + json.dumps({"at": "not-a-date", "reason": "legacy", "raw": "x"})
        + "\n",
        encoding="utf-8",
    )

    records = log.records()

    assert len(records) == 1
    assert records[0].id
    assert records[0].at is None
