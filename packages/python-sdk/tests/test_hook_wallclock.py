"""End-to-end hook wall-clock tests (M29 DEP-3, #443; PRD 50).

The in-process budget (≤5 ms/step) is CPU cost; the latency a developer feels is
the **process-spawn cost of a fresh hook interpreter, twice per tool call**. This
publishes and gates that number per OS, with a stated user-visible budget and a
500-call session overhead figure. Windows is blocked on WIN-1 (named-pipe
transport re-pointed to M31) and reported as such, never silently measured.
"""

from __future__ import annotations

import sys
from pathlib import Path

from agentwatch import hook_perf
from agentwatch.perf import PerfStats

REPO = Path(__file__).resolve().parents[3]
WORKFLOW = REPO / ".github" / "workflows" / "hook-perf.yml"
DOC = REPO / "docs" / "reference" / "performance.md"
SCRIPT = REPO / "scripts" / "hook_perf_gate.py"


def _stats(p99: float = 40.0) -> PerfStats:
    return PerfStats(
        iterations=20, mean_ms=p99 * 0.8, p50_ms=p99 * 0.6, p99_ms=p99, max_ms=p99 * 1.2
    )


def test_detect_os() -> None:
    assert hook_perf.detect_os("darwin") == "macos"
    assert hook_perf.detect_os("linux") == "linux"
    assert hook_perf.detect_os("linux2") == "linux"
    assert hook_perf.detect_os("win32") == "windows"


def test_measure_cheap_command() -> None:
    wallclock = hook_perf.measure_hook_wallclock(
        command=sys.executable,
        args=("-c", "pass"),
        iterations=3,
        budget_ms=100_000.0,
    )

    assert wallclock.blocked is False
    assert wallclock.stats.iterations == 3
    assert wallclock.stats.p99_ms >= 0.0
    assert wallclock.within_budget is True
    assert wallclock.os_name in {"macos", "linux", "windows"}


def test_windows_is_blocked_not_measured() -> None:
    wallclock = hook_perf.measure_hook_wallclock(os_name="windows", iterations=1)

    assert wallclock.blocked is True
    assert wallclock.within_budget is False
    assert wallclock.block_reason is not None and "WIN-1" in wallclock.block_reason
    assert wallclock.stats.iterations == 0


def test_budget_violation_is_detected() -> None:
    wallclock = hook_perf.measure_hook_wallclock(
        command=sys.executable,
        args=("-c", "import time; time.sleep(0.05)"),
        iterations=3,
        budget_ms=1.0,
    )

    assert wallclock.within_budget is False
    code, violations = hook_perf.evaluate_hook(wallclock, None)
    assert code == 1
    assert any("budget" in violation for violation in violations)


def test_evaluate_flags_drift_above_the_band() -> None:
    wallclock = hook_perf.HookWallclock(os_name="linux", stats=_stats(50.0), budget_ms=1000.0)

    code, violations = hook_perf.evaluate_hook(wallclock, baseline_p99=10.0, tolerance=3.0)

    assert code == 1
    assert any("drift" in violation for violation in violations)


def test_evaluate_accepts_a_blocked_os() -> None:
    wallclock = hook_perf.measure_hook_wallclock(os_name="windows", iterations=1)

    code, violations = hook_perf.evaluate_hook(wallclock, None)

    assert code == 0
    assert violations == []


def test_session_overhead_quote() -> None:
    wallclock = hook_perf.HookWallclock(os_name="linux", stats=_stats(40.0), budget_ms=1000.0)

    assert wallclock.per_tool_call_ms == 80.0
    assert wallclock.session_overhead_ms() == 80.0 * 500
    assert wallclock.session_overhead_seconds() == 40.0


def test_generated_block_is_deterministic_and_idempotent() -> None:
    wallclock = hook_perf.HookWallclock(os_name="macos", stats=_stats(40.0), budget_ms=1000.0)

    block = hook_perf.render_block([wallclock])
    assert block == hook_perf.render_block([wallclock])
    assert "macos" in block
    assert "500" in block

    text = f"# Doc\n\n{hook_perf.BEGIN_MARKER}\nold\n{hook_perf.END_MARKER}\n"
    once = hook_perf.replace_marker_block(text, block)
    twice = hook_perf.replace_marker_block(once, block)
    assert once == twice
    assert "old" not in once


def test_doc_has_the_generated_hook_block() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert hook_perf.BEGIN_MARKER in text and hook_perf.END_MARKER in text
    assert "End-to-end hook" in text
    assert "500-call" in text


def test_ci_workflow_gates_the_hook_wallclock() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/hook_perf_gate.py" in text
    assert "macos" in text
    assert "windows" in text
    assert "WIN-1" in text or "blocked" in text.lower()


def test_gate_script_exists() -> None:
    assert SCRIPT.is_file()
    assert "hook_perf" in SCRIPT.read_text(encoding="utf-8")
