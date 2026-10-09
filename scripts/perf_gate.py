#!/usr/bin/env python3
"""Performance-budget gate (PRD 38 §Q4, issue #221).

NFR-1 is "≤5 ms per step". ``tests/test_perf_budget.py`` measures it once inside
pytest; this gate makes it *enforced and published*: it measures the recording
stages, compares each p99 against a committed baseline within a documented
tolerance band, and fails when the NFR cap is exceeded or the path drifts. The
published number is generated from the run (``docs/reference/performance.md`` is
produced by ``--update-baseline``, never hand-written).

Usage:
    python scripts/perf_gate.py                 # gate: fail on violation
    python scripts/perf_gate.py --self-test     # prove a slowdown fails the gate
    python scripts/perf_gate.py --update-baseline [--write-doc]

Environment note: CI machine variance is absorbed by DRIFT_TOLERANCE; the NFR cap
is absolute. Refresh the baseline on the same runner class when the code changes.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO / "perf" / "baseline.json"
LATEST_PATH = REPO / "perf" / "latest.json"
DOC_PATH = REPO / "docs" / "reference" / "performance.md"

# NFR-1: the synchronous per-step budget. Absolute, not tunable by tolerance.
NFR_BUDGET_MS = 5.0
# Machine variance / scheduling noise band. A drift beyond this (vs the committed
# baseline) is a regression. Documented here and surfaced in the published doc.
DRIFT_TOLERANCE = 3.0
# Stages whose p99 is below this floor are too fast for a meaningful relative
# drift check (microbenchmark noise on shared runners); the absolute NFR cap still
# protects them. Without a floor, a 0.01 ms stage would "regress" at 0.03 ms.
DRIFT_FLOOR_MS = 2.0


def _pre_message(span: int = 1) -> dict[str, Any]:
    return {
        "phase": "pre",
        "harness": "claude-code",
        "event": {
            "session_id": "perf",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_use_id": f"perf-{span}",
            "timestamp": "2026-01-02T03:04:05+00:00",
        },
    }


def _measure_normalize(iterations: int) -> float:
    from agentwatch.adapters import claude_code
    from agentwatch.perf import time_call

    return time_call(lambda: claude_code.normalize(_pre_message()), iterations=iterations).p99_ms


def _measure_redaction(iterations: int) -> float:
    from agentwatch.perf import time_call
    from agentwatch.secrets import redact_mapping

    args = {"command": "ls", "token": "sk-abcdefghijklmnop", "note": "hello"}
    return time_call(lambda: redact_mapping(args), iterations=iterations).p99_ms


def _measure_daemon(iterations: int) -> float:
    from agentwatch.daemon import Daemon
    from agentwatch.perf import time_call
    from agentwatch.store import RecordStore

    root = Path(tempfile.mkdtemp(prefix="agentwatch-perf-"))
    daemon = Daemon(
        socket_path=root / "d.sock",
        store=RecordStore(root / "records.jsonl", durability="none"),
        records_path=root / "records.jsonl",
    )
    counter = {"n": 0}

    def step() -> None:
        counter["n"] += 1
        daemon.handle_message(_pre_message(counter["n"]))

    return time_call(step, iterations=iterations).p99_ms


def _measure_otlp_protobuf(iterations: int) -> float:
    """One bare OTLP protobuf message -> records (M26 OTEL-3)."""
    from agentwatch.ingest import transcode_otlp_protobuf
    from agentwatch.perf import time_call
    from opentelemetry.proto.collector.trace.v1 import trace_service_pb2
    from opentelemetry.proto.common.v1 import common_pb2
    from opentelemetry.proto.trace.v1 import trace_pb2

    request = trace_service_pb2.ExportTraceServiceRequest(
        resource_spans=[
            trace_pb2.ResourceSpans(
                scope_spans=[
                    trace_pb2.ScopeSpans(
                        spans=[
                            trace_pb2.Span(
                                trace_id=bytes.fromhex("11" * 16),
                                span_id=bytes.fromhex("22" * 8),
                                name="execute_tool",
                                start_time_unix_nano=1_767_000_000_000_000_000,
                                end_time_unix_nano=1_767_000_001_000_000_000,
                                attributes=[
                                    common_pb2.KeyValue(
                                        key="gen_ai.tool.name",
                                        value=common_pb2.AnyValue(string_value="execute_tool"),
                                    )
                                ],
                            )
                        ]
                    )
                ]
            )
        ]
    )
    data = request.SerializeToString()
    return time_call(lambda: transcode_otlp_protobuf(data), iterations=iterations).p99_ms


def _measure_live_tail(iterations: int) -> float:
    """One live-tail reconciliation poll (M26 STR-2)."""
    from agentwatch.live import LiveTail
    from agentwatch.perf import time_call
    from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
    from agentwatch.store import RecordStore

    root = Path(tempfile.mkdtemp(prefix="agentwatch-perf-live-"))
    path = root / "records.jsonl"
    store = RecordStore(path, durability="none")
    for index in range(50):
        store.append(
            AgentRecord(
                session_id="perf",
                agent=AgentIdentity(identity="perf"),
                tool=ToolCall(name="Bash"),
                outcome=Outcome.OK,
                started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                span_id=f"sp{index}",
            )
        )
    return time_call(lambda: LiveTail(path).poll(), iterations=iterations).p99_ms


def _measure_detector_eval(iterations: int) -> float:
    """One run of the rule-detector field-test matrix (M26 DET-2)."""
    from agentwatch.perf import time_call

    analytics_src = str(REPO / "services" / "analytics" / "src")
    # Force *this* checkout's analytics package to the front and drop any cached
    # modules, so a same-named install on the path cannot shadow it.
    for name in [m for m in list(sys.modules) if m == "analytics" or m.startswith("analytics.")]:
        del sys.modules[name]
    if analytics_src in sys.path:
        sys.path.remove(analytics_src)
    sys.path.insert(0, analytics_src)
    import asyncio

    from analytics.scenario_validation import run_rule_matrix

    calls = max(1, min(iterations, 3))
    return time_call(lambda: asyncio.run(run_rule_matrix()), iterations=calls).p99_ms


SCENARIOS: dict[str, Callable[[int], float]] = {
    "normalize": _measure_normalize,
    "redaction": _measure_redaction,
    "daemon_handle_message": _measure_daemon,
    "otlp_protobuf": _measure_otlp_protobuf,
    "live_tail_poll": _measure_live_tail,
    "detector_eval": _measure_detector_eval,
}

# Per-scenario budgets (NFR-1 for the recording path; the new M26 paths get
# their own absolute cap derived from the design contract).
SCENARIO_BUDGETS_MS: dict[str, float] = {
    "normalize": NFR_BUDGET_MS,
    "redaction": NFR_BUDGET_MS,
    "daemon_handle_message": NFR_BUDGET_MS,
    "otlp_protobuf": 10.0,
    "live_tail_poll": 25.0,
    "detector_eval": 8000.0,
}


def scenario_budget(name: str) -> float:
    """The absolute cap (ms) for a scenario."""
    return SCENARIO_BUDGETS_MS.get(name, NFR_BUDGET_MS)


def measure(iterations: int) -> dict[str, float]:
    """Measure p99 (ms) for every scenario."""
    return {name: fn(iterations) for name, fn in SCENARIOS.items()}


def evaluate(
    measured: dict[str, float],
    baseline: dict[str, float],
    *,
    budget_ms: float = NFR_BUDGET_MS,
    tolerance: float = DRIFT_TOLERANCE,
) -> tuple[int, list[str]]:
    """Return (exit_code, violations) comparing measured p99 to cap and baseline."""
    violations: list[str] = []
    for name, p99 in sorted(measured.items()):
        cap = scenario_budget(name)
        if p99 > cap:
            violations.append(f"{name}: p99 {p99:.3f} ms > budget {cap:.3f} ms")
        committed = baseline.get(name)
        if committed is not None:
            threshold = max(committed * tolerance, DRIFT_FLOOR_MS)
            if p99 > threshold:
                violations.append(
                    f"{name}: p99 {p99:.3f} ms > drift threshold {threshold:.3f} ms "
                    f"(baseline {committed:.3f} ms x{tolerance:.1f}, floor {DRIFT_FLOOR_MS} ms)"
                )
    return (1 if violations else 0), violations


def _render_doc(measured: dict[str, float], generated_at: str) -> str:
    rows = "\n".join(
        f"| `{name}` | {p99:.3f} | {scenario_budget(name):.1f} | {baseline.get(name, float('nan')):.3f} |"
        for name, p99 in sorted(measured.items())
    )
    return (
        "# Reference — Performance\n\n"
        "**BLUF:** The recording path's p99 latency, measured by `scripts/perf_gate.py` "
        "and generated from a run — not written by hand.\n\n"
        f"Generated: {generated_at} · recording stages budget **≤{NFR_BUDGET_MS:.0f} ms per step** (NFR-1); "
        f"new M26 paths carry their own per-scenario caps · drift tolerance: **{DRIFT_TOLERANCE:.1f}×** above a "
        f"**{DRIFT_FLOOR_MS:.1f} ms** floor\n\n"
        "| Stage | measured p99 (ms) | budget (ms) | committed baseline p99 (ms) |\n"
        "|---|---|---|---|\n"
        f"{rows}\n\n"
        "> Regenerate with `python scripts/perf_gate.py --update-baseline --write-doc` on the "
        "reference runner class. Recording budgets are absolute (NFR-1); the new-path caps and the "
        "drift tolerance absorb machine variance. See [performance-budget](../design/performance-budget.md).\n"
    )


def _load_baseline() -> dict[str, float]:
    if not BASELINE_PATH.exists():
        return {}
    data: dict[str, Any] = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {key: float(value) for key, value in data.get("baseline_ms", {}).items()}


def _write_baseline(measured: dict[str, float], *, write_doc: bool) -> None:
    generated_at = datetime.now(timezone.utc).isoformat()
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "budget_ms": NFR_BUDGET_MS,
                "tolerance": DRIFT_TOLERANCE,
                "baseline_ms": measured,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if write_doc:
        global baseline
        baseline = dict(measured)
        DOC_PATH.write_text(_render_doc(measured, generated_at), encoding="utf-8")


# Populated by --update-baseline so _render_doc can show the committed baseline.
baseline: dict[str, float] = _load_baseline()


def _run_self_test() -> int:
    from agentwatch.perf import time_call

    # A deliberately slowed "normalize": 10 ms/step blows the 5 ms NFR cap.
    def slowed() -> None:
        time.sleep(0.010)

    def normalize_slow() -> None:
        from agentwatch.adapters import claude_code

        slowed()
        claude_code.normalize(_pre_message())

    measured = {"normalize": time_call(normalize_slow, iterations=50).p99_ms}
    code, violations = evaluate(measured, baseline)
    if code != 1 or not violations:
        print("self-test FAILED: a deliberate slowdown did not trip the gate")
        return 1
    print(f"self-test OK: slowdown tripped the gate ({violations[0]})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--write-doc", action="store_true", help="with --update-baseline")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return _run_self_test()

    measured = measure(args.iterations)

    if args.update_baseline:
        _write_baseline(measured, write_doc=args.write_doc)
        print(f"baseline written to {BASELINE_PATH.relative_to(REPO)}")
        for name, p99 in sorted(measured.items()):
            print(f"  {name}: p99 {p99:.3f} ms")
        return 0

    LATEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "budget_ms": NFR_BUDGET_MS,
                "tolerance": DRIFT_TOLERANCE,
                "measured_ms": measured,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    committed = _load_baseline()
    code, violations = evaluate(measured, committed)
    for name, p99 in sorted(measured.items()):
        base = committed.get(name)
        base_text = f"{base:.3f}" if base is not None else "n/a"
        print(f"  {name}: p99 {p99:.3f} ms (baseline {base_text} ms)")
    if code != 0:
        print("performance gate FAILED:", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
    else:
        print("performance gate passed")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
