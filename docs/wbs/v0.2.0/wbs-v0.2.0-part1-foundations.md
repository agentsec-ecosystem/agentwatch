# WBS v0.2.0 — Part 1: Foundations (M25)

**BLUF:** M25 lands everything the later milestones build on: AAT export + mapping, OTel agent-span alignment, the
agent-identity dimension, the detector eval harness, the streaming transport, the first real captures (Cursor,
Gemini), the SDK restructure, the cross-harness test kit, and the launch-blocking naming mitigations.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **WBS updated** · **issues updated** · **code committed and pushed to
> `feat-v0.2.0`** · design docs updated.

---

## Milestone M25 — Foundations (PRD 40–48)

**Status:** 🚧 in progress — **done:** 25.SCHEMA-1 (#424), 25.IDN-1 (#299), 25.AAT-1 (#295), 25.AAT-2
(#296), 25.OTEL-1 (#297), 25.OTEL-2 (#298), 25.TRACE-1 (#300), 25.STR-1 (#301), 25.DET-1 (#302), 25.CUR-2
(#304, native-hooks adapter on documented shapes), 25.GEM-1 (#305), 25.SDK-1..3 (#306–#308), 25.XHT-1
(#309), 25.XHT-4 (#310), 25.NAM-1 (#312, incl. ADR-0026 decision), and the M25 tail 25.CLI-1/25.CFG-1/25.CI-1
(#425–#427); 25.FLD-1a (#370 plan drafted). **Blocked:** 25.CUR-1 (#303) — requires a consented live Cursor
capture; it cannot be produced in CI. **Open:** 25.RSK-1 (#311), 25.T (#371), 25.D (#372), 25.R (#373).

**Goal:** Establish the standards, identity, sampling, streaming, and test-kit foundations, and begin real
harness capture — so M26 can complete the standards loop and prove the claims.

**Requirements / PRDs:** [PRD 40](../../prd/40-v0.2.0-program.md) · [PRD 41](../../prd/41-standards-and-interop-ii.md) ·
[PRD 42](../../prd/42-harness-fidelity-and-realtime.md) · [PRD 43](../../prd/43-detector-credibility-and-evaluation.md) ·
[PRD 44](../../prd/44-identity-enterprise-and-compliance.md) · [PRD 46](../../prd/46-platform-sdk-and-growth.md) ·
[PRD 47](../../prd/47-cross-harness-testkit.md) · [PRD 48](../../prd/48-v0.2.0-risks-testing-and-decisions.md).

**Work items**

| # | Task | Deliverable | Dependencies | Acceptance | Issue |
|---|---|---|---|---|---|
| 25.AAT-1 | Pin AAT draft revision + record↔AAT mapping incl. `record_phase` + identity fields | mapping + code + contract test | PRD 23 (records), PRD 31 (verifier) | Mapping table reviewed; `lossless-or-explicit` enforced by the validator; a missing field is `unmapped`, never invented | #295 |
| 25.AAT-2 | `export-session --format aat` | feature + tests | 25.AAT-1 | Output validates against published AAT fixtures; lossless round-trip verified by 26.AAT-3 | #296 |
| 25.OTEL-1 | Re-pin semconv to `semantic-conventions-genai`; align operations; pin in `--version`/resources; drift check | feature + tests + CI job | S39 W4 pin pattern | Canonical agent-span operations used; a simulated upstream bump fails the drift check | #297 |
| 25.OTEL-2 | Privacy-mode ↔ OTel content-capture mapping | docs + property test | 25.OTEL-1 | No content escapes the active privacy mode on export | #298 |
| 25.IDN-1 | `agent_identity` dimension (name/version/harness/model/workload-id ref/credential class) | schema + feature + tests | PRD 35 (S14/S29) | Property test: identity fields never contain secret material; principals hashed by default | #299 |
| 25.TRACE-1 | `traceparent` on records; propagation through subagents, MCP proxy, SDK spans | feature + tests | 25.IDN-1, MCP proxy (N1) | A subagent span and its parent record share one trace id | #300 |
| 25.STR-1 | Daemon→API/UI push transport (UDS/WS); append-then-verify preserved; bounded queues | feature + tests | store (M4), S10 pattern | Drop-consumer test: no store loss; `degraded` surfaced on backpressure | #301 |
| 25.DET-1 | `agentwatch detectors eval` harness + corpus v0 (internal) | feature + tests | PRD 30 (L1) | Reproduction is deterministic; seeds pinned; one command, offline | #302 |
| 25.CUR-1 | Authenticated Cursor capture → scrub → version-tagged golden fixtures | fixtures + capture script | PRD 27 (I2) | ≥2 version-tagged sets; automated secret scan green on the committed corpus | #303 |
| 25.CUR-2 | Cursor native-hooks adapter (full loop incl. Tab/workspace hooks) | adapter + conformance pack | 25.CUR-1, O1 | Conformance pack green; blocking events recorded as observations never answered; IDE/CLI/remote tagged; cloud-agent gaps declared | #304 |
| 25.GEM-1 | Gemini native-OTel ingest recipe (`otlpEndpoint`/`outfile` → `ingest --format otel`) | recipe + tests | 25.OTEL-1 | A captured telemetry file ingests to validated records; redaction mandatory on the logPrompts path | #305 |
| 25.SDK-1 | `AgentWatchProvider` + processors + `shutdown`/`flush(timeout)` at-most-once + no-op semantics | feature + tests | PRD 05, DD-12 | Exit/crash tests prove flush; `@trace_agent` unchanged (DD-12) | #306 |
| 25.SDK-2 | Security-relevant-always-on sampler (deterministic; visible to `coverage`) | feature + property test | 25.SDK-1, S2 | Security events never sampled; determinism holds across replays; `sampled-out` marker recorded | #307 |
| 25.SDK-3 | Concurrency guarantees tested; `telemetry.sdk.*`/`service.*` attributes; SDK conformance pack | feature + tests | 25.SDK-1 | Documented guarantees; pack registered in O1 | #308 |
| 25.XHT-1 | Harness payload corpus + `replay-fixtures` runner wired into O1 | fixtures + runner + tests | PRD 27 (N3), PRD 42 | `--self-test` proves a deliberately broken adapter fails; every registered adapter ships ≥ N fixtures | #309 |
| 25.XHT-4 | Compatibility-matrix fidelity tiers (`live-verified \ | fixture-verified \ | modeled`) | generator + docs | PRD 27 (N4) |
| 25.RSK-1 | Fuzz/property/mutation extensions for new parsers, incl. the Codex #36937 regression seed | tests | PRD 48 §2 | Weaponized input is contained, never executed; parsers never spawn shells | #311 |
| 25.NAM-1 | Naming mitigations: qualified installs, distribution-check warning, namesake FAQ | docs + guard test | [ADR-0026](../../adr/0026-naming-decision.md) | A bare-name install attempt produces a loud warning; FAQ merged; **ADR-0026 decision recorded** | #312 |
| 25.FLD-1a | Field-test plan drafted | plan doc | PRD 40 §5 | `docs/field-test/v0.2.0/` plan exists with the case roster | #370 |
| 25.SCHEMA-1 | v0.2.0 record/schema additions + spec + data dictionary | schema + spec + data dict | PRD 15/23, PRD 39 (W5) | Additive fields/events in schema/, record-format-spec, data dictionary; forward-compat fixture | #424 |
| 25.CLI-1 | CLI reference + error contract + launcher updates | docs + code | M25-M28 features | New subcommands/flags documented; error catalog extended; npx launcher updated | #425 |
| 25.CFG-1 | Config keys + `config explain` docs for new features | feature + docs | PRD 16 (S34) | New keys layered, fail-closed, explainable; no secret values printed | #426 |
| 25.CI-1 | Wire the new CI workflows | CI jobs | PRD 48 §2, PRD 38 | AAT drift, harness drift, cross-parser, Windows, soak, detector eval, compliance report, AAT vectors all run | #427 |
| 25.T | Add/expand test cases for this milestone | tests | M25 feature tickets | All new paths covered; coverage ≥ 95% | #371 |
| 25.D | Create/update the design + reference docs for this milestone | docs | M25 feature tickets | Docs updated and linked from the WBS | #372 |
| 25.R | Code review & risk sign-off for this milestone | review | M25 feature tickets + 25.T + 25.D | Review recorded; no unresolved findings | #373 |

**Work-item detail**

- **25.AAT-1** decomposes into: (a) the field mapping table; (b) the `record_phase` provenance field; (c) the
  identity-field mapping (consumes 25.IDN-1); (d) the validator change enforcing `lossless-or-explicit`. Files:
  `schema/` (vectors), adapter/export module, PRD 41 §AAT-1. Design: [aat-mapping.md](../../design/aat-mapping.md).
- **25.SDK-1** decomposes into: provider class; redact→chain→export processor pipeline; batch-processor defaults
  (queue/scheduled-delay/max-batch); `shutdown`/`flush`; no-op-after-shutdown; context-manager form. Design:
  [sdk-lifecycle.md](../../design/sdk-lifecycle.md).
- **25.STR-1** decomposes into: socket/WS transport; bounded per-subscriber queue; `degraded` state; append path
  untouched. Design: [streaming-views.md](../../design/streaming-views.md).
- **25.XHT-1** decomposes into: corpus layout; replay runner; O1 integration; `--self-test`; per-harness fixture
  seeds. Design: [cross-harness-testing.md](../../design/cross-harness-testing.md).

**Tests required:** per-item tests as listed; fuzz/property/mutation for every new trust-path component; coverage
≥ 95% on AAT mapping, provider/sampler, streaming transport, Cursor/Gemini adapters.

**Evidence artifacts (milestone close):** AAT export fixture + validation log; OTel agent-span tree in a reference
backend; identity property-test output; streaming drop-consumer report; Cursor/Gemini conformance-pack results;
SDK flush/crash test log; replay-fixtures `--self-test` output; ADR-0026 decision record.

**Risks & mitigations:** R1 standard churn → version-pin + drift (AAT-5/OTEL-1); R4 harness instability →
version-tagged corpus; R8 scope → cut-line enforced; R11 naming → NAM-1 is launch-blocking.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · WBS + issues updated · pushed to `feat-v0.2.0`
- [ ] **All relevant documents are updated as the milestone is closed out** (see "Documents to update at
      close-out" below)
- [ ] AAT export validates against fixtures; OTel agent-span tree renders in ≥1 reference backend; identity
      property test green; streaming survives a consumer crash; Cursor/Gemini conformance packs registered; SDK
      flush proven.
- [ ] NAM-1 complete and ADR-0026 **decided** (launch-blocking).

**Documents to update at close-out:** the design docs listed below, plus [PRD 41](../../prd/41-standards-and-interop-ii.md),
[PRD 42](../../prd/42-harness-fidelity-and-realtime.md), [PRD 46](../../prd/46-platform-sdk-and-growth.md),
[PRD 47](../../prd/47-cross-harness-testkit.md), [CHANGELOG](../../../CHANGELOG.md), [README](../../../README.md),
[reference/compatibility.md](../../reference/compatibility.md) (fidelity tiers), and
[reference/known-limitations.md](../../reference/known-limitations.md) where a gap's proving test lands.

**Design docs to update:** [aat-mapping.md](../../design/aat-mapping.md) · [agent-identity.md](../../design/agent-identity.md) ·
[streaming-views.md](../../design/streaming-views.md) · [sdk-lifecycle.md](../../design/sdk-lifecycle.md) ·
[cross-harness-testing.md](../../design/cross-harness-testing.md) · [otel-mapping.md](../../design/otel-mapping.md) ·
[harness-adapter-design.md](../../design/harness-adapter-design.md) — updated or accepted at this milestone.

---
