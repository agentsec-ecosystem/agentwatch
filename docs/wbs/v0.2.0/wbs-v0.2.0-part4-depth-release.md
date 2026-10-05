# WBS v0.2.0 — Part 4: Depth (M28)

**BLUF:** M28 lands the depth items: the derived Postgres tier (phaseable to v0.2.x), injection/memory
observations, retention + signed default, the remaining capture surfaces (A2A, system effects, ACS, TS spike),
governance motions, and registry interop. **Field tests and release readiness are the dedicated last two
milestones (M29–M30) — see [Part 5](wbs-v0.2.0-part5-field-test-release.md).**

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **WBS updated** · **issues updated** · **code committed and pushed to
> `feat-v0.2.0`** · design docs updated.

---

## Milestone M28 — Depth (PRD 40–48)

**Status:** ⏳ not started

**Goal:** Complete the remaining depth items and capture surfaces. Field tests (M29) and release readiness (M30)
follow — do not tag in M28. Items phased to v0.2.x are listed explicitly (never silently dropped).

**Requirements / PRDs:** [PRD 40](../../prd/40-v0.2.0-program.md) · [PRD 41](../../prd/41-standards-and-interop-ii.md) ·
[PRD 43](../../prd/43-detector-credibility-and-evaluation.md) · [PRD 44](../../prd/44-identity-enterprise-and-compliance.md) ·
[PRD 45](../../prd/45-new-capture-surfaces.md) · [PRD 46](../../prd/46-platform-sdk-and-growth.md) ·
[PRD 48](../../prd/48-v0.2.0-risks-testing-and-decisions.md).

**Work items**

| # | Task | Deliverable | Acceptance | Issue |
|---|---|---|---|---|
| 28.PG-1 | Derived, rebuildable Postgres index; drop-Postgres CI mode | feature + CI | `--rebuild` reproduces the index bit-for-bit; `verify-store` never consults Postgres | #353 |
| 28.PG-2 | Multi-tenant isolation for the self-hosted console + API | feature + tests | Cross-tenant read returns nothing and is `store-access`-recorded | #354 |
| 28.PG-3 | SDK spans → unified store with the S11 `union` fallback | feature + tests | `source: sdk` distinction preserved; ordering/identity design in ADR-0019 | #355 |
| 28.DET-6 | Injection-shaped-content heuristics (deterministic; high-FP rules off by default) | feature + tests | Published precision/recall; opt-in defaults documented | #356 |
| 28.DET-7 | Agent memory-surface records + `search --memory` | feature + tests | Privacy modes respected; metadata always; inherited G9 gap closed with proving test | #357 |
| 28.COR-3 | `evidence <id> --include incident-report.json` (registry-shaped, redacted) | feature + tests | Validates against a schema fixture; redaction receipts attached; a test proves no auto-egress path exists | #358 |
| 28.COR-4 | Registry/postmortem mining into cited, shape-synthesized fixtures (standing practice) | fixtures + changelog | Every fixture cites a public source; synthesized only; changelog per addition | #359 |
| 28.CMP-3 | Retention profiles (`high-risk-12mo` per AAT §9, `general-6mo`, custom) driving `retention apply` | feature + tests | Changes recorded (S5); a missed run degrades visibly; report cites retention compliance | #360 |
| 28.CMP-4 | ed25519 signed default posture: rotation story; verification in `verify-store`/`evidence`/AAT; `doctor` state | feature + tests | Rotation is a recorded chain event; tampered signature fails; missing key reports "signed by key id X, key unavailable" | #361 |
| 28.OTEL-4 | Skills + command-execution spans where harnesses expose them | feature + tests | Fixture-backed; declared gap where not exposed | #362 |
| 28.IDN-4 | Credential-hygiene observation (shared/ambient flag) + AIMS/WIMSE/NCCoE mapping doc | feature + docs | Precision/recall via the DET harness; opt-in; mapping published | #363 |
| 28.A2A-1 | A2A interposition proxy (tasks, messages, artifacts, agent-card exchanges) | feature + conformance | Round-trip both directions; consent + byte-identical restore; conformance per spec version | #364 |
| 28.A2A-2 | Signed agent-card provenance + `agent-delegation` observation; `tree`/`trace` cross-org | feature + tests | Card verification outcome recorded (never assumed); CUJ-20 end-to-end | #365 |
| 28.SYS-1 | System-effects ingest (AgentSight/Tracee-shaped), Linux, opt-in | feature + tests | Lineage false-join precision published; lower layer never silently trusted; `source: system-ingest` labeled | #366 |
| 28.ACS-1 | ACS Guardian audit-trail ingest (+ emit-side spike) | feature + tests | Decisions → `denied`/`policy-fired` with pre-execution provenance; monitor-only preserved; spec version pinned | #367 |
| 28.TSS-1 | TypeScript SDK ADR + schema-portability spike (generate TS types from `schema/`) | ADR + contract test | ADR merged; round-trip contract test; ship decision deferred to v0.3.0 | #368 |
| 28.GOV-1 | Public plugin API (semver); `agent_exec_trace` codemod; contribution guide; ADR series complete | docs + codemod + tests | Codemod tested vs migration-guide examples; versioning statement in the compatibility policy | #369 |
| 28.DATA-1 | Data dictionary + derived-index Postgres schema | docs + DDL | Tables with source_seq/hash back-refs; derived-only | #435 |
| 28.MIG-1 | Migration guide v0.1.0 → v0.2.0 | docs | Upgrade verified from a frozen v0.1.0 store | #436 |
| 28.T | Add/expand test cases for this milestone | tests | All new paths covered; coverage ≥ 95% | #380 |
| 28.D | Create/update the design + reference docs for this milestone | docs | Docs updated and linked from the WBS | #381 |
| 28.R | Code review & risk sign-off for this milestone | review | Review recorded; no unresolved findings | #382 |

> **Moved to Part 5:** the v0.2.0 field-test execution/report (was 28.FLD-1b) is **M29.2/29.3**; the release
> gate, release notes, compatibility table, and security audit (was 28.REL) are **M30.3–30.8**. Do not tag in M28.

**Phased to v0.2.x (explicit, not dropped):** PG-1..3 (first to slip if M28 overruns) · A2A-1..2 · SYS-1 · ACS-1 ·
TSS-1 (spike only) · DET-6..7 · CMP-3..4 · OTEL-4 · COR-2..4. Phased items keep their issue open and re-pointed;
the chain store remains the source of truth regardless.

**Tests required:** bit-for-bit rebuild + no-Postgres leg; tenant-denial audit; injection/memory privacy tests;
retention/report integration; signed-rotation test; A2A conformance; coverage ≥ 95% on all new modules.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · WBS + issues updated · pushed to `feat-v0.2.0`
- [ ] **All relevant documents are updated as the milestone is closed out** (see "Documents to update at
      close-out" below)
- [ ] Postgres tier rebuilds bit-for-bit; injection/memory observations published with precision/recall; retention
      profiles + signed default live; A2A/SYS/ACS/TS shipped or explicitly phased; governance motions landed.
- [ ] Field tests and release readiness **not started** in M28 (they are M29–M30).

**Documents to update at close-out:** the design docs listed below, plus all PRDs 40–48 (status → shipped),
[ROADMAP.md](../../../ROADMAP.md), [docs/README.md](../../README.md), [CHANGELOG.md](../../../CHANGELOG.md),
[README.md](../../../README.md), [reference/compatibility.md](../../reference/compatibility.md),
[reference/known-limitations.md](../../reference/known-limitations.md),
[reference/comparison.md](../../reference/comparison.md), [gtm.md](../../gtm.md), and
[maintenance-backlog.md](../../maintenance-backlog.md).

**Design docs to update:** [derived-postgres.md](../../design/derived-postgres.md) ·
[detector-evaluation.md](../../design/detector-evaluation.md) · [threat-model.md](../../design/threat-model.md) ·
[harness-adapter-design.md](../../design/harness-adapter-design.md) · [known-limitations.md](../../reference/known-limitations.md) ·
[compatibility.md](../../reference/compatibility.md) · [comparison.md](../../reference/comparison.md).

---
