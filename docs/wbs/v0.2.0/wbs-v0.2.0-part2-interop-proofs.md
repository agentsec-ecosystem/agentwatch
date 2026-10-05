# WBS v0.2.0 — Part 2: Interop & Proofs (M26)

**BLUF:** M26 completes the standards loop and proves the claims: AAT ingest + conformance vectors, OTLP/gRPC,
cross-host trace reconstruction, live operator views + soak, published detector numbers, identity end-to-end, the
compliance-report engine, gateway recipes, OpenAPI, and the threat-model/ADR register.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **WBS updated** · **issues updated** · **code committed and pushed to
> `feat-v0.2.0`** · design docs updated.

---

## Milestone M26 — Interop & Proofs (PRD 41–44, 46–48)

**Status:** ⏳ not started

**Goal:** Close the standards round-trip, prove cross-agent/real-time/detector/identity claims, ship the compliance
engine, and land the risk/ADR register.

**Requirements / PRDs:** [PRD 41](../../prd/41-standards-and-interop-ii.md) · [PRD 42](../../prd/42-harness-fidelity-and-realtime.md) ·
[PRD 43](../../prd/43-detector-credibility-and-evaluation.md) · [PRD 44](../../prd/44-identity-enterprise-and-compliance.md) ·
[PRD 46](../../prd/46-platform-sdk-and-growth.md) · [PRD 47](../../prd/47-cross-harness-testkit.md) ·
[PRD 48](../../prd/48-v0.2.0-risks-testing-and-decisions.md).

**Work items**

| # | Task | Deliverable | Acceptance | Issue |
|---|---|---|---|---|
| 26.AAT-3 | `ingest --format aat` + quarantine of non-normalizable records | feature + tests | Foreign chains validated before storage; unmappable records quarantined with a reason (B4) | #313 |
| 26.AAT-4 | AAT conformance vectors in `schema/vectors/` + a second independent verifier | vectors + CI | Two independent verifiers agree on the vector table (Q6 pattern); divergence fails | #314 |
| 26.AAT-5 | AAT draft-revision drift check + re-pin policy | CI job + docs | A simulated draft bump fails the pin check and opens an issue | #315 |
| 26.OTEL-3 | OTLP/gRPC + protobuf ingest, streaming | feature + tests | 100 MB ingest completes within a memory bound; JSON path unchanged | #316 |
| 26.TRACE-2 | `agentwatch trace <tid>` cross-host reconstruction via fleet + clock-skew handling | feature + tests | 3-host/3-harness synthetic scenario → one ordered chain; broker gaps classified per host | #317 |
| 26.CUR-3 | Cursor coverage reconciliation vs transcripts | feature + tests | Gap classes extend the S2 taxonomy; no `unexplained` on the golden corpus | #318 |
| 26.STR-2 | `agentwatch tail -f`; live timeline + live anomaly inbox; back-fill reconciliation | feature + tests | p99 hook→view ≤ 1 s (perf gate); every gap classified; `degraded` visible | #319 |
| 26.STR-3 | Soak with a streaming consumer | CI job | 24 h green; bounded queues enforced; no store loss | #320 |
| 26.DET-2 | Re-scope/rewrite the 28 silent rule detectors; retire or reclassify with reasons | code + tests | ≥ 80% of rule detectors non-silent on the corpus | #321 |
| 26.DET-3 | Per-detector precision/recall generated into `detector-catalog.md` | docs + CI guard | Docs-drift impossible; claims-ledger entries present | #322 |
| 26.COR-1 | Public detector-eval corpus v1 (benchmark cases + field-test scenarios + benign FP traffic) | corpus + manifest | No real secrets/PII (governance scan); per-case verdicts machine-checkable; corpus version pinned in every number | #323 |
| 26.IDN-2 | Delegation-chain capture (on-behalf-of) where exposed; `search --identity` | feature + tests | Honest `unknown` where not exposed; AAT export populated | #324 |
| 26.IDN-3 | Attribution end-to-end in `impact`/`blame`/`tree`/`trace` | feature + tests | Multi-agent fixture answers the full attribution question in one command (CUJ-16) | #325 |
| 26.CMP-1 | `compliance report` engine (control → evidence command → verdict → refs → retention/signature status) | feature + tests | Zero unverifiable claims; executable-docs gate extended to report output | #326 |
| 26.CMP-2 | Framework templates: eu-ai-act-art12, iso-42001, iso-27001, soc2, nist-800-92 | templates + tests | Offline run; every row regenerable (CUJ-18) | #327 |
| 26.GWY-1 | LiteLLM/Portkey OTel ingest recipes | recipe + CI tests | Canonical `gen_ai.*` spans → records; no new adapters (D-Q) | #328 |
| 26.GWY-2 | Exact gateway cost attribution, source-stamped | feature + tests | `cost` output distinguishes exact vs estimated | #329 |
| 26.API-1 | OpenAPI publication + drift-checked typed client | OpenAPI + client + CI | `openapi.json` in repo; client contract test fails on drift | #330 |
| 26.XHT-2 | Live soak on OpenCode (pinned model, scratch repo) via plugin hooks | CI job + adapter row | Nightly soak green hermetically; discovered quirks feed 25.XHT-1; OpenCode matrix row added | #331 |
| 26.RSK-2 | Threat-model additions (5 rows) + ADRs 0016–0026 merged with features | docs + ADRs | Every matrix row references a test; all ADRs accepted | #332 |
| 26.UI-1 | Operator UI: live timeline + live anomaly inbox + streaming tail | feature + tests | Consume STR; back-fill on reconnect; `degraded` visible | #428 |
| 26.SEC-1 | Security baseline + threat-model traceability + recorder attack matrix | docs | Rows for every new surface; each linked to a test | #429 |
| 26.PERF-1 | Extend the perf harness + budgets for new paths | feature + CI | Streaming/ingest/eval budgets; performance.md regenerated | #430 |
| 26.T | Add/expand test cases for this milestone | tests | All new paths covered; coverage ≥ 95% | #374 |
| 26.D | Create/update the design + reference docs for this milestone | docs | Docs updated and linked from the WBS | #375 |
| 26.R | Code review & risk sign-off for this milestone | review | Review recorded; no unresolved findings | #376 |

**Tests required:** AAT vector table + dual-verifier; OTLP/gRPC ingest; trace reconstruction; streaming
reconciliation + soak; eval harness reproducibility; compliance-report regeneration; recipe CI; cross-parser
(XHT-3 moves to M27).

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · WBS + issues updated · pushed to `feat-v0.2.0`
- [ ] **All relevant documents are updated as the milestone is closed out** (see "Documents to update at
      close-out" below)
- [ ] AAT round-trips losslessly with an external consumer; detector numbers published with corpus + method;
      compliance report runs offline and every row regenerates; streaming p99 ≤ 1 s; cross-host trace reconstructs.
- [ ] Content gates: known-limitations G1/G2 leave with proving tests; claims-ledger entries for every number.

**Documents to update at close-out:** the design docs listed below, plus [PRD 41](../../prd/41-standards-and-interop-ii.md),
[PRD 43](../../prd/43-detector-credibility-and-evaluation.md), [PRD 44](../../prd/44-identity-enterprise-and-compliance.md),
[PRD 47](../../prd/47-cross-harness-testkit.md), [PRD 48](../../prd/48-v0.2.0-risks-testing-and-decisions.md),
[reference/detector-catalog.md](../../reference/detector-catalog.md), [reference/compatibility.md](../../reference/compatibility.md),
[reference/known-limitations.md](../../reference/known-limitations.md), [CHANGELOG](../../../CHANGELOG.md).

**Design docs to update:** [aat-mapping.md](../../design/aat-mapping.md) (vectors) ·
[streaming-views.md](../../design/streaming-views.md) (soak/reconciliation) ·
[detector-evaluation.md](../../design/detector-evaluation.md) (publication) ·
[threat-model.md](../../design/threat-model.md) (v0.2.0 rows).

---
