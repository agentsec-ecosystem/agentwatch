#!/usr/bin/env python3
"""Deep-audit a field-test run: verify *evidence*, not just verdicts (M23).

For every case in a run directory it inspects the artifacts and flags:

  * infrastructure failures (recorder-up / daemon-up / emit / store-has-records)
  * a `pass` with no store records, no container log, or no captured LLM I/O
    for LLM cases
  * negative assertions (expected-failure checks like `! agentwatch verify-store`)
    so a reader can distinguish "command failed as intended" from "test failed"

Usage:
    python3 scripts/fieldtest/audit-results.py [RUN_DIR]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
RESULTS_ROOT = REPO_ROOT / "field-test" / "v0.1.0" / "results"
REGISTRY = HERE / "cases" / "registry.json"

INFRA = {"recorder-up", "daemon-up", "emit", "store-has-records"}

LLM_KINDS = {"llm", "llm_validation", "synthetic_llm"}


def _registry() -> dict[str, dict[str, str]]:
    try:
        return {c["id"]: c for c in json.loads(REGISTRY.read_text())}
    except (OSError, ValueError):
        return {}


def _newest_run_dir() -> Path | None:
    runs = sorted(p for p in RESULTS_ROOT.iterdir() if p.is_dir()) if RESULTS_ROOT.exists() else []
    return runs[-1] if runs else None


def audit_case(case_dir: Path, kind: str) -> dict[str, object]:
    verdict_path = case_dir / "verdict.json"
    flags: list[str] = []
    result: dict[str, object] = {"id": case_dir.name, "status": "fail", "flags": flags}
    if not verdict_path.exists():
        flags.append("no-verdict")
        return result

    verdict = json.loads(verdict_path.read_text())
    result["status"] = verdict.get("status", "fail")
    assertions = verdict.get("assertions", [])
    result["assertions"] = assertions
    failed = [a["name"] for a in assertions if not a.get("ok")]
    result["failed_assertions"] = failed

    for name in failed:
        if name in INFRA:
            flags.append(f"infra-fail:{name}")

    store = case_dir / "artifacts" / "store"
    records = store / "records.jsonl"
    record_lines = 0
    if records.exists():
        record_lines = sum(1 for line in records.read_text(errors="ignore").splitlines() if '"seq":' in line)
    result["store_records"] = record_lines
    result["has_daemon_log"] = (store / "daemon.log").exists()
    result["has_container_log"] = (store / "container.log").exists()
    result["has_llm_io"] = (store / "test-llm-io.jsonl").exists()

    # A recorder case that passed but recorded nothing is a hollow pass.
    if kind not in LLM_KINDS and result["status"] == "pass" and "store-has-records" not in {
        a["name"] for a in assertions
    } and record_lines == 0:
        flags.append("pass-without-records")

    if kind in LLM_KINDS:
        if result["status"] == "pass" and not (result["has_llm_io"] or (case_dir / "artifacts").exists()):
            flags.append("llm-pass-without-io")
        if not result["has_llm_io"] and not any((case_dir / "artifacts").glob("**/llm_responses.json")):
            flags.append("llm-io-not-captured")

    logs = list((case_dir / "artifacts" / "logs").glob("*.log")) if (case_dir / "artifacts" / "logs").exists() else []
    result["log_files"] = [p.name for p in logs]
    return result


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    run_dir = Path(args[0]) if args else _newest_run_dir()
    if run_dir is None or not run_dir.exists():
        print("audit-results: no run directory found", file=sys.stderr)
        return 1
    registry = _registry()

    rows = []
    for case_dir in sorted((run_dir / "cases").glob("*")):
        if not case_dir.is_dir():
            continue
        kind = registry.get(case_dir.name, {}).get("kind", "")
        rows.append(audit_case(case_dir, kind))

    passed = [r for r in rows if r["status"] == "pass"]
    failed = [r for r in rows if r["status"] != "pass"]
    flagged = [r for r in rows if r["flags"]]

    print(f"# Deep audit — {run_dir.name}")
    print(f"cases={len(rows)} pass={len(passed)} fail={len(failed)} flagged={len(flagged)}\n")
    print("| Case | Status | Records | Failed assertions | Flags |")
    print("|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['id']} | {r['status']} | {r['store_records']} | "
              f"{', '.join(r['failed_assertions']) or '-'} | {', '.join(r['flags']) or '-'} |")

    (run_dir / "audit.json").write_text(json.dumps(rows, indent=2, default=str) + "\n")
    print(f"\naudit written to {run_dir}/audit.json")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
