"""Guard the built distribution artifacts (issue #14).

Skipped on a clean checkout (``dist/`` is git-ignored); run ``python -m build``
first. When a wheel is present, it must expose the ``agentwatch`` console script
and ship the CLI package.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

DIST = Path(__file__).resolve().parents[1] / "dist"


def _wheel() -> Path:
    wheels = sorted(DIST.glob("agentwatch-*.whl"))
    if not wheels:
        pytest.skip("no built wheel; run `python -m build packages/python-sdk`")
    return wheels[-1]


def test_sdist_is_built() -> None:
    if not list(DIST.glob("agentwatch-*.tar.gz")):
        pytest.skip("no built sdist; run `python -m build packages/python-sdk`")
    assert list(DIST.glob("agentwatch-*.tar.gz"))


def test_wheel_exposes_console_script() -> None:
    wheel = _wheel()
    with zipfile.ZipFile(wheel) as zf:
        entries = [name for name in zf.namelist() if name.endswith("entry_points.txt")]
        assert entries, "wheel is missing entry_points.txt"
        text = zf.read(entries[0]).decode("utf-8")
    assert "agentwatch = agentwatch.cli:main" in text


def test_wheel_ships_the_cli_package() -> None:
    wheel = _wheel()
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    assert "agentwatch/cli/main.py" in names
    assert "agentwatch/cli/__main__.py" in names
