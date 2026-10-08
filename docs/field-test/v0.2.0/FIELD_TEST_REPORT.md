# agentwatch v0.2.0 — Field Test Report

> **Generated:** TBD from `field-test/v0.2.0/results/`.
> **Overall:** TBD.
> **Structure:** mirrors the [v0.1.0 report](../v0.1.0/FIELD_TEST_REPORT.md) and the plan's §13 template,
> extended for the v0.2.0 suites and the `P/F|D` declare class.

---

## BLUF + Release Gate Verdict

TBD.

### Release gate verdict

TBD — the 16 PRD 40 §5 / §5-expanded items, each `pass` / `fail` / `declared` (+ named limitation).

---

## Environment

TBD — per-OS, per-suite fingerprints (`env.json`); OMLX model; backend versions (Jaeger/Tempo/collector).

---

## What Was Tested

TBD.

- **Layer 0 regression gate** — the v0.1.0 50-case field suite + 226 detector scenarios + the Playwright web
  suite; must be green before any v0.2.0 case is evaluated.
- **v0.2.0 field suites** — install/deployability/attestation · standards/interop · harness fidelity & real-time ·
  detector credibility/corpus/redaction · identity/compliance/SIEM · new capture surfaces · platform/SDK/interfaces/
  policy · authorization/oversight · capability supply chain & memory · code provenance · console & embedded query
  tier · governance/hold/notice · investigation & browser verification · outcomes/runner/demo/alert recipes ·
  hostile data / claims ledger / release-gate closure.
- **94 new cases** across S1–S15 (19 `P/F|D`); combined with Layer 0: **50 + 226 + 49 + 94 = 419 checks**.

---

## Scenario Results (Master Table)

TBD — all 94 rows with `pass|fail|declared` and the evidence path
(`field-test/v0.2.0/results/<suite>/<case>/`).

---

## Per-Suite Results

### S1 — Install / Deployability / Attestation

TBD.

### S2 — Standards & Interop

TBD.

### S3 — Harness Fidelity & Real-Time

TBD.

### S4 — Detector Credibility / Corpus / Redaction

TBD.

### S5 — Identity / Compliance / SIEM

TBD.

### S6 — New Capture Surfaces

TBD.

### S7 — Platform / SDK / Interfaces / Policy

TBD.

### S8 — Authorization / Oversight

TBD.

### S9 — Capability Supply Chain / Memory

TBD.

### S10 — Provenance / Agent Trace

TBD.

### S11 — Console / Embedded Index

TBD.

### S12 — Governance / Hold / Notice

TBD.

### S13 — Investigation / Browser Verification / Incident Cases

TBD.

### S14 — Outcomes / Runner / Demo / Alert Recipes

TBD.

### S15 — Hostile Data / Claims Ledger / Release-Gate Closure

TBD.

---

## Detector & Redaction Published-Numbers Reproduction

TBD — FT-DET / FT-COR / FT-RED; local numbers vs the published precision/recall, method and CIs cited.

---

## CUJ-15–34 + CUJ-8 Extension Verification

TBD — each CUJ ↔ proving case(s) ↔ verdict (plan §8).

---

## Playwright UI & Screenshot Recapture (analyst web + local console)

TBD. Two browser UIs are exercised; both recapture screenshots for v0.2.0.

- **Analyst web UI** — `apps/web/tests/e2e/*.spec.ts` (dashboard, fleet, timeline, anomalies, compare, a11y,
  acceptance, screenshots). `screenshots.spec.ts` recaptures the 8 user-guide images into
  `docs/assets/screenshots/` (`FT_SCREENSHOT_DIR`): `dashboard-overview`, `dashboard-to-fleet`, `fleet-default`,
  `timeline-normal`, `timeline-spans`, `anomalies-default`, `anomalies-critical`, `compare-deltas`.
- **Local console** (`agentwatch ui`, FT-LUI-1/2; PRD 54, CUJ-24) — `apps/web/tests/e2e/console.spec.ts`, run against
  a live console by `scripts/fieldtest/console_playwright.py`, captures `console-overview` / `console-signatures` and
  runs the axe gate.

Record here: the image inventory written to `docs/assets/screenshots/`, Playwright `passed/total` per spec (and the
count reconciliation against the plan's "49"), axe violations (target 0 serious/critical), and the console
**UI == CLI `--json`** parity result.

---

## Root Cause Analysis

TBD — every defect, in the v0.1.0 style (symptom → cause → fix → regression evidence).

---

## Defect Catalogue

TBD — one row per defect: id, suite/case, severity, status, fix commit, regression test.

---

## Issues Found & Fixed During Validation

TBD — issues opened/fixed during the run (and their tracking issue numbers).

---

## Observations

TBD — v0.1.0-style articles (what worked / what didn't / synthetic vs real).

---

## Learnings

TBD — numbered, actionable (as in the v0.1.0 report).

---

## Takeaways

TBD.

---

## Deferred Items (not v0.2.0 gates)

TBD — items explicitly phased to v0.2.x (e.g. PG-1..3 → v0.2.1), each named with its target milestone.

---

## Coverage, Gaps, and Declared Limitations

TBD — coverage per suite; the **declared register** (case → named limitation → release-gate item that permits
"or declared"); and any residual gaps.

---

## Claims Ledger + Known-Limitations Shrink Evidence

TBD — claims-ledger status; G1/G2/G4/G7/G8 removed with proving tests; carried-forward limitations named.

---

## Certification / Standards Conformance

TBD — EU AI Act Art. 12 / ISO 42001 / ISO 27001 / SOC 2 / NIST-800-92 / OWASP ASI-2026 + AST10 (offline, per-row
evidence commanded); non-certification statement.

---

## Performance & Timings

TBD — end-to-end hook cost per OS (FT-DEP-3), streaming p99 (FT-STR-1), and the timing table from
`reference/performance.md`.

---

## Results & Coverage Comparison (v0.1.0 → v0.2.0)

TBD — checks, suites, detector numbers, and the known-limitations delta.

---

## Action Items

TBD.

---

## Reproducibility / Evidence Paths

TBD — exact commands to reproduce each suite, and the evidence paths under
`field-test/v0.2.0/results/<suite>/<case>/` (`commands.log`, `stdout.log`, `stderr.log`, `verdict.json`,
`assertions.ndjson`, `env.json`, `artifacts/`).

---

## Appendices

TBD — detector per-scenario breakdown, LLM telemetry, raw tables, and the fixture manifest
(`scripts/fieldtest/fixtures/*/manifest.json`).
