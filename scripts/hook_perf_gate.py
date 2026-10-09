#!/usr/bin/env python3
"""End-to-end hook wall-clock gate (M29 DEP-3, #443; PRD 50).

Publishes and gates the process-spawn cost a developer feels per tool call: the
real wall-clock of ``agentwatch-hook pre`` (two hooks per tool call) on macOS and
Linux, with a user-visible budget, a 500-call session overhead quote, and a
committed per-OS baseline. Windows is reported blocked on WIN-1 (named-pipe
transport re-pointed to M31), never silently measured.

Usage:
    python scripts/hook_perf_gate.py                       # gate current OS
    python scripts/hook_perf_gate.py --self-test           # prove a slowdown fails
    python scripts/hook_perf_gate.py --update-baseline --write-doc
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "python-sdk" / "src"))

from agentwatch import hook_perf  # noqa: E402
from agentwatch.perf import PerfStats  # noqa: E402

BASELINE_PATH = REPO / "perf" / "hook-e2e-baseline.json"
DOC_PATH = REPO / "docs" / "reference" / "performance.md"
OS_ORDER = ("macos", "linux", "windows")


def _load_baseline() -> dict[str, Any]:
    if not BASELINE_PATH.exists():
        return {"os": {}}
    try:
        data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"os": {}}
    return data if isinstance(data, dict) else {"os": {}}


def _entry(wallclock: hook_perf.HookWallclock) -> dict[str, Any]:
    return {
        "blocked": wallclock.blocked,
        "iterations": wallclock.stats.iterations,
        "mean_ms": wallclock.stats.mean_ms,
        "p50_ms": wallclock.stats.p50_ms,
        "p99_ms": wallclock.stats.p99_ms,
        "max_ms": wallclock.stats.max_ms,
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }


def _wallclock_from(name: str, data: dict[str, Any], budget: float) -> hook_perf.HookWallclock:
    entry = (data.get("os") or {}).get(name)
    if name == "windows" or entry is None or entry.get("blocked"):
        reason = "blocked on WIN-1" if name == "windows" else "pending CI"
        return hook_perf.HookWallclock(
            os_name=name,
            stats=PerfStats(iterations=0, mean_ms=0.0, p50_ms=0.0, p99_ms=0.0, max_ms=0.0),
            budget_ms=budget,
            blocked=True,
            block_reason=reason,
        )
    return hook_perf.HookWallclock(
        os_name=name,
        stats=PerfStats(
            iterations=int(entry.get("iterations", 0)),
            mean_ms=float(entry.get("mean_ms", 0.0)),
            p50_ms=float(entry.get("p50_ms", 0.0)),
            p99_ms=float(entry.get("p99_ms", 0.0)),
            max_ms=float(entry.get("max_ms", 0.0)),
        ),
        budget_ms=budget,
    )


def _write_doc(data: dict[str, Any]) -> None:
    budget = hook_perf.HOOK_P99_BUDGET_MS
    rows = [_wallclock_from(name, data, budget) for name in OS_ORDER]
    block = hook_perf.render_block(rows)
    text = DOC_PATH.read_text(encoding="utf-8")
    DOC_PATH.write_text(hook_perf.replace_marker_block(text, block), encoding="utf-8")


def _run_self_test() -> int:
    slow = hook_perf.measure_hook_wallclock(
        command=sys.executable,
        args=("-c", "import time; time.sleep(0.05)"),
        iterations=3,
        budget_ms=1.0,
    )
    code, violations = hook_perf.evaluate_hook(slow, None)
    if code != 1 or not violations:
        print("self-test FAILED: a deliberate slowdown did not trip the gate")
        return 1
    print(f"self-test OK: slowdown tripped the gate ({violations[0]})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--write-doc", action="store_true", help="with --update-baseline")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return _run_self_test()

    measured = hook_perf.measure_hook_wallclock(iterations=args.iterations)
    data = _load_baseline()
    baseline_p99 = ((data.get("os") or {}).get(measured.os_name) or {}).get("p99_ms")

    if args.update_baseline:
        os_data = data.setdefault("os", {})
        os_data[measured.os_name] = _entry(measured)
        data["generated_at"] = datetime.now(timezone.utc).isoformat()
        data["budget_ms"] = hook_perf.HOOK_P99_BUDGET_MS
        data["tolerance"] = hook_perf.DRIFT_TOLERANCE
        data["os"]["windows"] = {"blocked": True}
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if args.write_doc:
            _write_doc(data)
        print(f"baseline written for {measured.os_name}")
        return 0

    if measured.blocked:
        print(f"hook wall-clock: {measured.os_name} {measured.block_reason}")
        return 0

    code, violations = hook_perf.evaluate_hook(measured, baseline_p99)
    print(
        f"  {measured.os_name}: hook p50 {measured.stats.p50_ms:.1f} ms, "
        f"p99 {measured.stats.p99_ms:.1f} ms (budget {measured.budget_ms:.0f} ms; "
        f"500-call session {measured.session_overhead_seconds():.1f} s)"
    )
    if code != 0:
        print("hook wall-clock gate FAILED:", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
    else:
        print("hook wall-clock gate passed")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
