#!/usr/bin/env python3
"""Fill docs/field-test/v0.2.0/FIELD_TEST_REPORT.md from the run results.

Reads every field-test/v0.2.0/results/<suite>/cases/<ID>/verdict.json and the
Layer-0 (v0.1.0) results, then rewrites these report sections:

  * Scenario Results (Master Table)      -- every case: PASS | FAIL | not run
  * Per-Suite Results (S1..S15)          -- per-suite rollup
  * Root Cause Analysis                  -- one block per FAIL (evidence)
  * Defect Catalogue                     -- one row per FAIL

Status vocabulary is exactly **PASS | FAIL | not run** (per the run request).
`declared` (an unavailable P/F|D environment) is reported as `not run` with a
note, since it is neither a pass nor a fail.

Usage: python3 scripts/fieldtest/build_report.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "field-test" / os.environ.get("FT_VERSION", "v0.2.0") / "results"
V01 = REPO / "field-test" / "v0.1.0" / "results"
REGISTRY = REPO / "scripts/fieldtest/cases/registry.json"
REPORT = REPO / "docs/field-test/v0.2.0/FIELD_TEST_REPORT.md"

SUITES = [
    "s1-install", "s2-interop", "s3-harness", "s4-detectors", "s5-identity",
    "s6-surfaces", "s7-platform", "s8-apv", "s9-capability", "s10-provenance",
    "s11-console", "s12-governance", "s13-investigation", "s14-outcomes", "s15-hostile",
]


def _verdict(case_id: str) -> dict | None:
    for suite in SUITES:
        vp = RESULTS / suite / "cases" / case_id / "verdict.json"
        if vp.exists():
            try:
                v = json.loads(vp.read_text(encoding="utf-8"))
                v["_case_dir"] = str(vp.parent)
                return v
            except (OSError, json.JSONDecodeError):
                return None
    return None


def _status(verdict: dict | None) -> str:
    if verdict is None:
        return "not run"
    s = str(verdict.get("status", "fail"))
    if s == "pass":
        return "PASS"
    if s == "declared":
        return "not run"
    return "FAIL"


def _fail_evidence(case_id: str, verdict: dict) -> dict[str, str]:
    case_dir = Path(verdict.get("_case_dir", ""))
    failed: list[str] = []
    ap = case_dir / "assertions.ndjson"
    if ap.exists():
        for line in ap.read_text(encoding="utf-8").splitlines():
            try:
                a = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not a.get("ok", False):
                failed.append(str(a.get("name")))
    stderr = ""
    sp = case_dir / "stderr.log"
    if sp.exists():
        stderr = "\n".join(sp.read_text(encoding="utf-8", errors="replace").splitlines()[-12:])
    return {"failed_assertions": ", ".join(failed) or "(none recorded)",
            "case_dir": str(case_dir.relative_to(REPO)), "stderr_tail": stderr}


def _replace_section(text: str, heading: str, body: str) -> str:
    start = text.index(heading) + len(heading)
    nxt = text.find("\n## ", start)
    nxt = len(text) if nxt == -1 else nxt
    return text[:start] + "\n\n" + body.rstrip() + "\n" + text[nxt:]


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    cases = [c for c in registry if c.get("suite")]
    by_suite: dict[str, list[dict]] = {s: [] for s in SUITES}
    for c in cases:
        by_suite.setdefault(c["suite"], []).append(c)

    rows, fails = [], []
    counts = {"PASS": 0, "FAIL": 0, "not run": 0}
    for c in sorted(cases, key=lambda x: x["id"]):
        v = _verdict(c["id"])
        st = _status(v)
        counts[st] += 1
        rows.append((c["id"], c["suite"], c.get("class", "P/F"), st))
        if st == "FAIL":
            fails.append((c, v, _fail_evidence(c["id"], v or {})))

    # --- master table ---
    table = ["| Case | Suite | Class | Status |", "|---|---|---|---|"]
    for cid, suite, cls, st in rows:
        table.append(f"| {cid} | {suite} | {cls} | {st} |")
    table.append("")
    table.append(f"**Totals:** {counts['PASS']} PASS · {counts['FAIL']} FAIL · "
                 f"{counts['not run']} not run  (of {len(cases)} v0.2.0 cases).")

    # --- per-suite rollup ---
    per = []
    for s in SUITES:
        ids = by_suite.get(s, [])
        cp = cf = cn = 0
        for c in ids:
            st = _status(_verdict(c["id"]))
            cp += st == "PASS"; cf += st == "FAIL"; cn += st == "not run"
        per.append(f"### {s}\n\n{len(ids)} case(s): {cp} PASS · {cf} FAIL · {cn} not run\n")
    per_body = "\n".join(per)

    # --- RCA + defect catalogue (FAILs) ---
    rca, defects = [], ["| Case | Suite | Failed assertions | Evidence |", "|---|---|---|---|"]
    for c, _v, ev in fails:
        rca.append(
            f"### {c['id']} — {c['title']}\n\n"
            f"- **Suite:** {c['suite']} · **Class:** {c.get('class', 'P/F')}\n"
            f"- **Failed assertions:** {ev['failed_assertions']}\n"
            f"- **Evidence:** `{ev['case_dir']}`\n"
            f"- **stderr (tail):**\n\n```\n{ev['stderr_tail']}\n```\n\n"
            f"- **Cause:** TBD (from the evidence above)\n"
            f"- **Fix / regression:** TBD\n"
        )
        defects.append(f"| {c['id']} | {c['suite']} | {ev['failed_assertions']} | `{ev['case_dir']}` |")
    rca_body = "\n".join(rca) or "No failures recorded."
    if not fails:
        defects.append("| — | — | — | — |")

    # --- layer 0 rollup ---
    l0 = []
    for run in sorted(V01.glob("*/summary.json")) if V01.exists() else []:
        try:
            s = json.loads(run.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        t = s.get("totals", {})
        l0.append(f"- `{run.parent.name}`: {t.get('pass', 0)} PASS · {t.get('fail', 0)} FAIL")

    text = REPORT.read_text(encoding="utf-8")
    text = _replace_section(text, "## Scenario Results (Master Table)", "\n".join(table))
    text = _replace_section(text, "## Per-Suite Results", per_body)
    text = _replace_section(text, "## Root Cause Analysis", rca_body)
    text = _replace_section(text, "## Defect Catalogue", "\n".join(defects))
    if l0:
        text = text.replace(
            "TBD — the v0.1.0 50-case field suite + 226 detector scenarios + the Playwright web\n  suite; must be green before any v0.2.0 case is evaluated.",
            "Layer-0 (v0.1.0) results:\n" + "\n".join(l0),
        )
    REPORT.write_text(text, encoding="utf-8")
    print(f"report filled: {counts['PASS']} PASS / {counts['FAIL']} FAIL / "
          f"{counts['not run']} not run -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
