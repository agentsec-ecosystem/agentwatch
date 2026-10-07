"""GOV-1 codemod tests (M28, #369; PRD 46 §GOV-1).

The ``agent_exec_trace`` → ``agentwatch`` codemod is tested against the examples
in the v0.1.0 migration guide, so the documented upgrade path and the tool agree.
The legacy name is exactly what the repo guard forbids elsewhere; this file and
the codemod are allowlisted.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
CODEMOD = ROOT / "scripts" / "codemod_agent_exec_trace.py"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("codemod_agent_exec_trace", CODEMOD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_from_import_is_rewritten() -> None:
    # The exact migration-guide example.
    source = "from agent_exec_trace import AgentTracer, trace_agent, tool_span\n"

    rewritten, count = _module().codemod_source(source)

    assert rewritten == "from agentwatch import AgentTracer, trace_agent, tool_span\n"
    assert count == 1


def test_plain_and_aliased_imports_are_rewritten() -> None:
    rewritten, count = _module().codemod_source(
        "import agent_exec_trace\nimport agent_exec_trace as aet\n"
    )

    assert rewritten == "import agentwatch\nimport agentwatch as aet\n"
    assert count == 2


def test_submodule_and_attribute_references_are_rewritten() -> None:
    source = (
        "from agent_exec_trace.context import RunContext\n"
        "tracer = agent_exec_trace.tracer.AgentTracer()\n"
    )

    rewritten, count = _module().codemod_source(source)

    assert rewritten == (
        "from agentwatch.context import RunContext\ntracer = agentwatch.tracer.AgentTracer()\n"
    )
    assert count == 2


def test_strings_and_comments_are_left_alone() -> None:
    source = 'legacy = "agent_exec_trace"  # agent_exec_trace in a comment\n'

    rewritten, count = _module().codemod_source(source)

    assert rewritten == source
    assert count == 0


def test_cli_check_reports_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("import agent_exec_trace\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(CODEMOD), "--check", str(target)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert target.read_text(encoding="utf-8") == "import agent_exec_trace\n"


def test_cli_write_rewrites_in_place(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("import agent_exec_trace\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(CODEMOD), str(target)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert target.read_text(encoding="utf-8") == "import agentwatch\n"
