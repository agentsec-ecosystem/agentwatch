"""Guard the agentwatch distribution identity.

These assertions pin the published identity (issue #10): the distribution is
named ``agentwatch`` and it exposes the ``agentwatch`` console script, so a
rename or a dropped entry point cannot ship silently.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on 3.10 only
    import tomli as tomllib

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _metadata() -> dict[str, Any]:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def test_distribution_is_named_agentwatch() -> None:
    assert _metadata()["project"]["name"] == "agentwatch"


def test_console_script_points_at_cli_main() -> None:
    scripts = _metadata()["project"].get("scripts", {})
    assert scripts.get("agentwatch") == "agentwatch.cli:main"


def test_tomli_backport_is_declared_for_python_310() -> None:
    deps = _metadata()["project"]["dependencies"]
    assert any(dep.startswith("tomli") and "3.11" in dep for dep in deps)


def test_build_is_a_dev_dependency() -> None:
    dev = _metadata()["project"]["optional-dependencies"]["dev"]
    assert any(dep.startswith("build") for dep in dev)


def test_tomli_is_unconditional_in_dev() -> None:
    # mypy targets py3.10, so it imports tomli on every CI matrix leg; the dev
    # extra must therefore install it unconditionally or py3.12 typecheck fails.
    dev = _metadata()["project"]["optional-dependencies"]["dev"]
    assert any(dep.startswith("tomli") and "python_version" not in dep for dep in dev)
