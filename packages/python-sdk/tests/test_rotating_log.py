"""Rotated daemon log tests (M12 F6)."""

from __future__ import annotations

from pathlib import Path

from agentwatch.rotating_log import RotatingLog


def test_rotates_only_at_the_cap(tmp_path: Path) -> None:
    log = RotatingLog(tmp_path / "daemon.log", max_bytes=10, backups=2)
    with log.open_append() as handle:
        handle.write(b"short")
    assert not log.rotate()
    assert (tmp_path / "daemon.log").read_bytes() == b"short"


def test_rotation_shifts_backups(tmp_path: Path) -> None:
    log = RotatingLog(tmp_path / "daemon.log", max_bytes=5, backups=2)
    for content in (b"aaaaa", b"bbbbb", b"ccccc"):
        with log.open_append() as handle:
            handle.write(content)

    assert (tmp_path / "daemon.log").read_bytes() == b"ccccc"
    assert (tmp_path / "daemon.log.1").read_bytes() == b"bbbbb"
    assert (tmp_path / "daemon.log.2").read_bytes() == b"aaaaa"
    # The oldest beyond `backups` is dropped, never unbounded.
    assert not (tmp_path / "daemon.log.3").exists()
    assert len(log.backups_present()) == 2


def test_size_bytes_reports_current(tmp_path: Path) -> None:
    log = RotatingLog(tmp_path / "daemon.log", max_bytes=100)
    assert log.size_bytes() == 0
    with log.open_append() as handle:
        handle.write(b"12345")
    assert log.size_bytes() == 5
