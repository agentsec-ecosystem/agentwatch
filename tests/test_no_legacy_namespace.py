"""Repo guard: no stray legacy ``agent_exec_trace`` workspace references (WBS M0 0.T).

The namespace rename must leave the codebase free of the old package name. The
only permitted references are the DD-12 compatibility shim and its dedicated
test (PRD 10 §D requires the legacy import path to keep working). Historical and
migration docs are out of scope: they name the old project on purpose.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

LEGACY = "agent_exec_trace"
ROOT = Path(__file__).resolve().parents[1]

# DD-12 allowlist: the shim itself and the test that exercises it.
ALLOWLIST = {
    "packages/python-sdk/src/agent_exec_trace/__init__.py",
    "packages/python-sdk/tests/test_legacy_shim.py",
    "tests/test_no_legacy_namespace.py",
}

# Scan implementation + tests + configs, not historical/migration docs.
SCAN_PREFIXES = (
    "packages/",
    "services/",
    "apps/",
    "examples/",
    "scripts/",
    "tests/",
    "deploy/",
    "schema/",
    ".github/",
)
SCAN_FILES = {"pyproject.toml", "Makefile", "docker-compose.yml", ".pre-commit-config.yaml"}


def _tracked_text_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


def test_no_stray_legacy_namespace_references() -> None:
    offenders: list[str] = []
    for rel in _tracked_text_files():
        if rel in ALLOWLIST:
            continue
        if not (rel.startswith(SCAN_PREFIXES) or rel in SCAN_FILES):
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if LEGACY in text:
            offenders.append(rel)

    assert offenders == [], f"stray legacy namespace references: {offenders}"
