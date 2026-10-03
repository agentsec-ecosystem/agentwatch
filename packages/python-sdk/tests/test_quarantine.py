"""Tests for the quarantine log (M5 B4)."""

from __future__ import annotations

import os
from pathlib import Path

from agentwatch.quarantine import QuarantineLog


def test_add_preserves_the_raw_bytes(tmp_path: Path) -> None:
    log = QuarantineLog(tmp_path / "quarantine.jsonl")

    log.add("not json at all", reason="malformed-line")

    entries = log.entries()
    assert len(entries) == 1
    assert entries[0]["raw"] == "not json at all"
    assert entries[0]["reason"] == "malformed-line"


def test_quarantine_file_is_owner_only(tmp_path: Path) -> None:
    path = tmp_path / "quarantine.jsonl"
    log = QuarantineLog(path)

    log.add("x", reason="malformed-line")

    assert os.stat(path).st_mode & 0o777 == 0o600


def test_entries_skips_corrupt_lines(tmp_path: Path) -> None:
    path = tmp_path / "quarantine.jsonl"
    log = QuarantineLog(path)
    log.add("good", reason="r")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("not json\n")

    assert [entry["raw"] for entry in log.entries()] == ["good"]


def test_entries_is_empty_when_absent(tmp_path: Path) -> None:
    assert QuarantineLog(tmp_path / "nope.jsonl").entries() == []
