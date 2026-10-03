# WBS v0.1.0 — Part 9: Engineering Rigor & Evidence (M14–M15)

**BLUF:** Raise the engineering floor and turn records into third-party-trustable artifacts. PRDs 31–39, all in v0.1.0. Field Tests (M23) and Release Readiness (M24) remain the last two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M14 — Engineering Rigor (Q1–Q13)

**Status:** ☐ not started

**Goal:** Raise the engineering floor: property/differential/mutation/fuzz testing, whole-repo CI, an enforced performance budget, published conformance vectors, a forward-compatibility matrix, a machine-readable error contract, a claims ledger, executable docs, a WCAG level, time correctness, and a release pipeline that signs what it ships.

**Requirements / PRDs:** [PRD 38](../../prd/38-engineering-rigor.md) · full detail in the PRD sections.

**Work items**

| # | Task | Deliverable | Acceptance | Issue |
|---|---|---|---|---|
| 14.Q1 | Property-based + differential redaction testing | tests + CI/tooling | The property test fails on a seeded unredacted secret shape | #218 |
| 14.Q2 | Mutation testing on the trust path | tests + CI/tooling | CI fails when survivors exceed the budget | #219 |
| 14.Q3 | Fuzzing the parsers, now rather than before v1.0 | tests + CI/tooling | Each harness runs in CI | #220 |
| 14.Q4 | Enforce the performance budget in CI | tests + CI/tooling | A deliberate slowdown fails the gate | #221 |
| 14.Q5 | Make CI run the whole repo | tests + CI/tooling | The new jobs run green on the current tree | #222 |
| 14.Q6 | Publish conformance test vectors for the store and chain | tests + CI/tooling | `store.py` and the standalone verifier both match the expected-verdict table | #223 |
| 14.Q7 | Forward-compatibility test matrix for stored data | tests + CI/tooling | Every frozen store reads/verifies/replays/exports in CI | #224 |
| 14.Q8 | One machine-readable error contract | tests + CI/tooling | Every subcommand's failure path emits the envelope with a code | #225 |
| 14.Q9 | A claims ledger | tests + CI/tooling | The ledger check fails on a claim without an evidence link and passes on the current set | #226 |
| 14.Q10 | Executable documentation | tests + CI/tooling | The extracted-command job passes on the current docs | #227 |
| 14.Q11 | State an accessibility conformance level | tests + CI/tooling | A keyboard-only E2E traverses CUJ-8 | #228 |
| 14.Q12 | Time correctness as a tested property | tests + CI/tooling | Property tests over DST boundaries and non-UTC defaults pass | #229 |
| 14.Q13 | A release pipeline that actually signs what it ships | tests + CI/tooling | A dry-run release produces SBOM + signature + provenance | #230 |

**Tests required:** per-item tests as listed; all new paths covered; coverage ≥ 95%.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated
- [ ] Whole-repo CI green (web unit + axe + Playwright + no-network); perf gate enforced; release pipeline dry-run passes.

**Design docs to update:** [PRD 38](../../prd/38-engineering-rigor.md), [PRD 13](../../prd/13-non-functional-requirements.md), [PRD 18](../../prd/18-security-compliance.md), [CHANGELOG](../../../CHANGELOG.md)

---

## Milestone M15 — Evidence & Provenance (PRD 31)

**Status:** ☐ not started

**Goal:** Turn records into third-party-trustable artifacts: the offline-verifiable evidence bundle, a standalone verifier, the Agent BOM, record provenance, store-access audit, operator annotations, and redaction receipts.

**Requirements / PRDs:** [PRD 31](../../prd/31-evidence-and-provenance.md) · full detail in the PRD sections.

**Work items**

| # | Task | Deliverable | Acceptance | Issue |
|---|---|---|---|---|
| 15.S1 | `agentwatch evidence` — the self-contained, offline-verifiable incident bundle | feature + tests | Bundle → `evidence verify` round-trip offline | #231 |
| 15.S12 | A standalone, dependency-free bundle verifier | feature + tests | Both the shipped verifier and the doc reference implementation pass the same vectors; | #232 |
| 15.S9 | `agentwatch bom` — an Agent Bill of Materials per session (CycloneDX) | feature + tests | Generated BOM validates against the CycloneDX schema | #233 |
| 15.S26 | A `producer` field on every record | feature + tests | Round-trip with the field | #234 |
| 15.S21 | Log reads of the store, not just writes | feature + tests | `evidence`/`export-session` append exactly one `store-access` record with the scope | #235 |
| 15.S20 | `agentwatch annotate` — operator notes in the chain | feature + tests | Note round-trips as a record | #236 |
| 15.S32 | Redaction receipts — show the user what was dropped | feature + tests | A record with a masked secret and a dropped argument has both rules in its receipt | #237 |

**Tests required:** per-item tests as listed; all new paths covered; coverage ≥ 95%.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated
- [ ] `agentwatch evidence` bundle verifies offline; three verdicts independent; BOM validates against CycloneDX.

**Design docs to update:** [PRD 31](../../prd/31-evidence-and-provenance.md), [store-format](../../reference/store-format.md), [record-format spec](../../reference/record-format-spec.md)

---
