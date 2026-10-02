"""Tests for the ``@agentsec-ecosystem/cli`` npx launcher (issue #14).

The launcher is a thin shim that invokes the Python CLI, so ``npx
@agentsec-ecosystem/cli <command>`` behaves like ``agentwatch <command>``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLI_DIR = ROOT / "packages" / "cli"


def test_package_json_declares_agentwatch_bin() -> None:
    pkg = json.loads((CLI_DIR / "package.json").read_text(encoding="utf-8"))
    assert pkg["name"] == "@agentsec-ecosystem/cli"
    assert pkg["bin"]["agentwatch"] == "bin/agentwatch.js"
    assert (CLI_DIR / pkg["bin"]["agentwatch"]).is_file()


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_launcher_forwards_to_python_cli(tmp_path: Path) -> None:
    node = shutil.which("node")
    assert node is not None
    script = CLI_DIR / "bin" / "agentwatch.js"

    result = subprocess.run(
        [node, str(script), "--help"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "status" in result.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_launcher_forwards_exit_code(tmp_path: Path) -> None:
    node = shutil.which("node")
    assert node is not None
    script = CLI_DIR / "bin" / "agentwatch.js"

    result = subprocess.run(
        [node, str(script), "verify-store"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )

    assert result.returncode != 0
    assert "not implemented" in result.stderr.lower()
