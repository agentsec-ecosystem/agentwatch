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

TBD (results). Harness validation (deep in-container probe, pre-run) is recorded in the RCA/Defect sections.

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

Two classes of finding: **harness defects** (found during the pre-run deep in-container probe — a "stack up"
and direct `exec` into the recorder) and **product defects** (found by the cases themselves; filled from the run).

### H-1 — `ingest --format <harness>` values do not exist

**Symptom:** ingest-based cases (`cursor`, `gemini`, `mcp`, `a2a`, `gateway`, `xht`, `hostile`, `sdk-native`)
failed with `no such file/format`.

**Root cause:** the drivers called `agentwatch ingest --format <harness>`, but the shipped `ingest` accepts only
`--format {otel,otlp-grpc,ndjson,aat,claude-compliance,claude-otel,system-ingest,acs}` plus `--agent {codex,opencode}`.
A CLI command existing does **not** mean a given value exists. Cursor/Gemini ingest through their shipped adapters
(`agentwatch.adapters.cursor|gemini_cli.normalize`).

**Fix:** `ingest-fixture.py` now dispatches to the real format/agent/adapter surface (10 kinds verified in-container).

### H-2 — fixtures unreachable inside the container

**Symptom:** `/ft/fixtures/<kind>` "No such file or directory".

**Root cause:** the overlay mounted `./scripts/fieldtest → /ft/scripts` only; the fixtures live under
`scripts/fieldtest/fixtures`, so `/ft/fixtures` did not exist.

**Fix:** mount `./scripts/fieldtest/fixtures → /ft/fixtures:ro` on all 9 v0.2.0 services; verified with
`ls /ft/fixtures` (16 kinds) inside the recorder.

### H-3 — docker cases ran on the host

**Symptom:** `can't open file '/ft/scripts/fleet-run.py'` (FT-TRACE-1/2, FT-IDN-1, FT-A2A-1, FT-XHT-1/3/4).

**Root cause:** the step used `ft_assert … bash -lc …`, which runs on the host, where `/ft/scripts` does not exist.

**Fix:** switched to `ft_assert_recorder` (runs inside the recorder container).

### H-4 — driver flag mismatch (`otel-probe --mb`)

**Symptom:** `otel-probe.py: error: unrecognized arguments: --mb 100`.

**Root cause:** `otel-probe.py` supports `--endpoint/--service/--spans`, not `--mb`.

**Fix:** `otel_grpc_stream.py` uses `--spans`.

### H-5 — fixture shape mismatch

**Symptom:** `ingested 0 records … 2 problem(s)`; cursor/gemini normalized 0 records.

**Root cause:** the synthesized `foreign.aat.json` used an invented record shape (the AAT ingest expects
`aat_version`/`action_type`/`agentwatch`); the Cursor/Gemini fixtures are `{"message": {...}, "expected": [...]}`
wrappers, so the adapter must normalize `message`, not the wrapper.

**Fix:** build `foreign.aat.json` from `schema/vectors/aat/valid.json` records + one non-normalizable record;
`ingest-fixture.py` normalizes `message`. Verified: 10/10 kinds ingest, chain green.

### H-6 — step facts wrong (doctor / privacy / jaeger timing)

**Symptom:** FT-DEP-1, FT-OTEL-3, FT-OTEL-1 failed.

**Root cause:** `doctor` prints `hooks effective: no (not installed…)` (regex omitted `no`); the real default
capture is `metadata-only` (step grepped `truncated`); Jaeger registers the service a few seconds after export.

**Fix:** corrected the regex, the default value, and added a `sleep 8` before the Jaeger probe (verified: 3 spans
→ `['agentwatch','jaeger-all-in-one']`).

### H-7 — `declared` outcomes produced "not run"

**Symptom:** FT-WIN-1/FT-SYS-1/FT-TSS-1 resolved to `declared`.

**Root cause:** the declare branches short-circuited instead of exercising the case.

**Fix:** replaced with real assertions so every case yields **PASS or FAIL** (per the run request); `system-ingest`
runs in the Linux recorder container.

Product defects (if any) are appended from the run below this line.

---

## Defect Catalogue

| ID | Class | Suite/case | Severity | Status | Fix |
|---|---|---|---|---|---|
| H-1 | harness | s2–s7 (ingest cases) | high | ✅ fixed | real ingest format/agent/adapter dispatch |
| H-2 | harness | all docker cases | critical | ✅ fixed | mount fixtures at `/ft/fixtures` (9 services) |
| H-3 | harness | TRACE/IDN/A2A/XHT | high | ✅ fixed | host → `ft_assert_recorder` |
| H-4 | harness | FT-OTEL-2 | medium | ✅ fixed | `--spans` (not `--mb`) |
| H-5 | harness | AAT/CUR/GEM ingest | high | ✅ fixed | real AAT record shape; normalize `message` |
| H-6 | harness | DEP-1/OTEL-1/OTEL-3 | medium | ✅ fixed | correct regex / default / jaeger wait |
| H-7 | harness | WIN-1/SYS-1/TSS-1 | medium | ✅ fixed | declare → real PASS/FAIL |

Product defects: TBD (filled from the run).

---

## Issues Found & Fixed During Validation

TBD — issues opened/fixed during the run (and their tracking issue numbers).

---

## Observations

### What worked

The **deep in-container probe** (boot the full v0.2.0 stack, `exec` into the recorder, run each driver) is the
single most valuable check: it converts "the command exists" into "the surface works". It immediately showed that
7/9 ingest kinds worked and exactly which 2 did not, and why.

### What didn't work (all fixed)

Everything in the Defect Catalogue above — the harness was wired to an imagined interface (`ingest --format
<harness>`) and to paths that were never mounted (`/ft/fixtures`). Each was fixed from observed evidence, not
guesswork, and re-verified in the container.

### Harness vs product

Distinguish **harness defects** (my wiring: H-1…H-7) from **product defects** (the shipped code). The 0.1.0 lesson
"harness bugs masquerade as product failures" is the dominant signal here too; the RCA separates them so the
product defect count is not inflated.

---

## Learnings

1. **A CLI command existing does not mean a value exists.** `agentwatch ingest` exists, but `--format cursor`
   does not; only 8 formats + `--agent codex|opencode` do. Validate the *value*, not just the command.
2. **Probe the real container.** Static greps ("the mount count is 9", "the option is in the parser") prove
   nothing; `exec` into the recorder and run the driver. The gap only appears when the real surface is exercised.
3. **Fixtures must be reachable and in the parser's real shape.** A fixture directory is useless if it is not
   mounted where the driver reads it, or if its shape is invented (`foreign.aat.json` initially ingested 0 records).
4. **Harness bugs masquerade as product failures.** 7 of 7 pre-run failures were harness, not product. Separating
   the classes is what keeps the report honest.
5. **`declared` is not "done".** A case that cannot run is not a pass; per this run, no case may end as "not run".

(Product-signal learnings from the run are appended here.)

---

## Takeaways

TBD.

---

## Deferred Items (not v0.2.0 gates)

TBD — items explicitly phased to v0.2.x (e.g. PG-1..3 → v0.2.1), each named with its target milestone.

---

## Coverage, Gaps, and Declared Limitations

Status vocabulary is exactly **not run | PASS | FAIL**. `declared` is reported as **not run** (an unavailable
environment is neither a pass nor a fail) — but the run target is **every case PASS or FAIL**: the declare
branches were replaced with real assertions (H-7) so nothing resolves to "not run" for a *harness* reason.

TBD (coverage numbers from the run).

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
