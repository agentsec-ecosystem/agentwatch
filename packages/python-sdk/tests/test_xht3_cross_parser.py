"""XHT-3 cross-parser validation gate (M27 #352).

Our Codex rollout reader is diffed against two independent, pinned OSS parsers
(Python agent-history; Go agent-ouija) on a golden fixture. The full diff needs
the parsers checked out; the CI job (``.github/workflows/xht3-cross-parser.yml``)
clones them and sets ``AGENTWATCH_XHT3_DIR``. Locally the diff is skipped, but the
golden fixture is always replayed through our reader.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from agentwatch.codex_rollout import read_rollout

REPO = Path(__file__).resolve().parents[3]
GOLDEN = REPO / "packages" / "python-sdk" / "tests" / "fixtures" / "codex-cli" / "golden"
FIXTURE = GOLDEN / "rollout-codex-0.65.jsonl"
SCRIPT = REPO / "scripts" / "xht3_cross_validate.py"


def test_golden_fixture_replays_through_our_reader() -> None:
    read = read_rollout(FIXTURE)

    assert read.session_id == "rollout-2025-12-08T00-37-46-abc123"
    assert [record.tool.name for record in read.records] == [
        "shell",
        "shell",
        "apply_patch",
        "apply_patch",
    ]
    assert read.tokens == 124866
    assert read.dangling is False


def test_cross_parser_diff_has_no_unexplained_divergence() -> None:
    parsers_dir = os.environ.get("AGENTWATCH_XHT3_DIR")
    if not parsers_dir or not (Path(parsers_dir) / "agent-ouija").is_dir():
        pytest.skip("cross-parser corpora not provisioned (see xht3-cross-parser.yml)")

    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(SCRIPT), "--parsers-dir", parsers_dir],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
