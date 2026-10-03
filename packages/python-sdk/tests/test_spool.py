"""Tests for the hook spool (M5 F1)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from agentwatch.spool import Spool


def test_append_and_drain_round_trip(tmp_path: Path) -> None:
    spool = Spool(tmp_path / "s.spool")

    spool.append({"phase": "pre", "event": {"x": 1}})
    spool.append({"phase": "post", "event": {"x": 2}})

    lines = spool.drain()
    assert len(lines) == 2
    assert json.loads(lines[0])["phase"] == "pre"
    assert spool.drain() == []


def test_spool_file_is_owner_only(tmp_path: Path) -> None:
    path = tmp_path / "s.spool"
    Spool(path).append({"a": 1})

    assert os.stat(path).st_mode & 0o777 == 0o600


def test_cap_drops_oldest_frames(tmp_path: Path) -> None:
    spool = Spool(tmp_path / "s.spool", max_bytes=80)
    for index in range(10):
        spool.append({"n": index})

    lines = spool.drain()

    assert 0 < len(lines) < 10
    assert json.loads(lines[-1])["n"] == 9
