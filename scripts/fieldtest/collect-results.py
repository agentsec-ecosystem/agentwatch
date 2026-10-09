#!/usr/bin/env python3
"""Aggregate field-test case verdicts into summary.json / summary.md (M23).

Usage::

    python3 collect-results.py [RESULTS_DIR]

Reads every ``cases/<ID>/verdict.json`` under the run directory (default: the
newest under field-test/v0.1.0/results/) and writes ``summary.json`` and
``summary.md`` beside it. Results live under field-test/v0.1.0/results/; the
report is assembled from them, never the reverse.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Version-scoped results root: FT_RESULTS_ROOT wins, else field-test/<FT_VERSION>/results.
RESULTS_ROOT = Path(
    os.environ.get("FT_RESULTS_ROOT")
    or (REPO_ROOT / "field-test" / os.environ.get("FT_VERSION", "v0.1.0") / "results")
)
REGISTRY = Path(__file__).resolve().parent / "cases" / "registry.json"


def _expected_ids() -> list[str]:
    try:
        return [str(case["id"]) for case in json.loads(REGISTRY.read_text(encoding="utf-8"))]
    except (OSError, ValueError, KeyError):
        return []


def _newest_run_dir() -> Path | None:
    if not RESULTS_ROOT.exists():
        return None
    runs = sorted(p for p in RESULTS_ROOT.iterdir() if p.is_dir())
    return runs[-1] if runs else None


def collect(run_dir: Path, expected: list[str] | None = None) -> dict[str, object]:
    cases: list[dict[str, object]] = []
    for verdict_path in sorted(run_dir.glob("cases/*/verdict.json")):
        try:
            verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            verdict = {"id": verdict_path.parent.name, "status": "fail", "error": str(exc)}
        verdict.setdefault("id", verdict_path.parent.name)
        verdict.setdefault("status", "fail")
        cases.append(verdict)

    # No skips *within the requested set*: a requested case with no verdict is a
    # failure. Cases outside the requested set are "not run in this section".
    requested = expected if expected is not None else _expected_ids()
    present = {str(case.get("id")) for case in cases}
    for case_id in requested:
        if case_id not in present:
            cases.append(
                {
                    "id": case_id,
                    "status": "fail",
                    "error": "no verdict recorded (case did not run)",
                }
            )
    cases.sort(key=lambda case: str(case.get("id")))

    totals = {"pass": 0, "fail": 0, "declared": 0}
    for case in cases:
        status = str(case.get("status"))
        if status == "pass":
            totals["pass"] += 1
        elif status == "declared":
            # Allowed only for P/F|D cases whose release gate says "or declared".
            totals["declared"] += 1
        else:
            case["status"] = "fail"
            totals["fail"] += 1

    env_path = run_dir / "env.json"
    env: dict[str, object] = {}
    if env_path.exists():
        try:
            env = json.loads(env_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            env = {}

    return {
        "run_id": run_dir.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "env": env,
        "totals": totals,
        "green": totals["fail"] == 0 and cases != [],
        "cases": cases,
    }


def render_markdown(summary: dict[str, object]) -> str:
    lines = [f"# Field Test Run {summary['run_id']}", ""]
    totals = summary["totals"]
    lines.append(
        f"**Totals:** {totals['pass']} pass · {totals['fail']} fail · "
        f"{totals.get('declared', 0)} declared  →  "
        f"**{'GREEN' if summary['green'] else 'NOT GREEN'}**"
    )
    lines.append("")
    lines.append("| Case | Class | Status |")
    lines.append("|---|---|---|")
    for case in summary["cases"]:
        lines.append(
            f"| {case.get('id')} | {case.get('class', 'P/F')} | {case.get('status')} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    expected: list[str] | None = None
    if "--expect" in args:
        index = args.index("--expect")
        expected = args[index + 1 :]
        args = args[:index]
    run_dir = Path(args[0]) if args else _newest_run_dir()
    if run_dir is None or not run_dir.exists():
        print("collect-results: no run directory found", file=sys.stderr)
        return 1
    summary = collect(run_dir, expected)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (run_dir / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
    totals = summary["totals"]
    print(
        f"collect-results: {totals['pass']} pass / {totals['fail']} fail / "
        f"{totals.get('declared', 0)} declared -> {run_dir}/summary.{{json,md}}"
    )
    return 0 if summary["green"] else 1


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
