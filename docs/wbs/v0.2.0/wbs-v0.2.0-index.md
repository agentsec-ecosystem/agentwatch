# WBS — agentwatch v0.2.0 (Index)

**BLUF:** **v0.2.0 turns the shipped record layer into the best-in-class one** (PRD 40–48). Eight work tracks
plus per-milestone supporting tickets, across **six milestones (M25–M30)**, every ticket with an owner PRD, a
deliverable, an acceptance seed, an issue number, and a fidelity/honesty gate. This index is the ticket source;
the five part files carry the milestone-level detail (Goal · Requirements · Work-item tables · Tests · Evidence ·
Exit criteria · Design docs).

**Parent:** agentsec-ecosystem #209 · **Program:** [PRD 40](../../prd/40-v0.2.0-program.md) · **Branch:**
`feat-v0.2.0`.

## Standard milestone exit criteria (applies to EVERY milestone)

**Closure acceptance criteria — all must be met before a milestone is declared complete:**

- [ ] **All tests pass** (`make test`)
- [ ] **Full test coverage ≥ 95%** (enforced in CI, no waivers)
- [ ] **Lint strict check clean** — `ruff` zero violations; `mypy --strict` clean
- [ ] **WBS updated** — every ticket checked off in the part file; status notes current; deferred items re-pointed
      to a named milestone (never silently dropped)
- [ ] **Issues updated** — every ticket has a tracking issue; issues closed or re-pointed to match the WBS
- [ ] **All relevant documents are updated as the milestone is closed out** — every affected PRD, design doc,
      reference doc, `CHANGELOG.md`, `README.md`, compatibility matrix, and `known-limitations.md` reflects the
      closed milestone (no doc left describing the pre-milestone state)
- [ ] **Code committed and pushed to the feature branch** (`feat-v0.2.0`) — working tree clean; CI green on the
      pushed HEAD

**Content gates (also required at every milestone):**

- [ ] **Design docs updated** (milestone-specific list in each part file)
- [ ] **Conformance pack registered** (O1) for every new adapter/reader/ingest format
- [ ] **Claims-ledger entry** for every public claim (including numbers)
- [ ] **Known-limitations line** added/removed **with the proving test**
- [ ] **Threat-model line** if the feature touches the trust boundary
- [ ] **Compatibility-matrix tier** updated (`live-verified | fixture-verified | modeled`)

## Milestones

| M | Name | PRDs | Part file |
|---|---|---|---|
| **M25** | Foundations (AAT export, OTel spans, identity, sampling, streaming, captures, test kit, naming) | 40–48 | [Part 1](wbs-v0.2.0-part1-foundations.md#milestone-m25--foundations-prd-4048) |
| **M26** | Interop & Proofs (AAT ingest/vectors, OTLP/gRPC, trace, live views, detector numbers, identity, compliance, threat/ADR register) | 41–44, 46–48 | [Part 2](wbs-v0.2.0-part2-interop-proofs.md#milestone-m26--interop--proofs-prd-4144-4648) |
| **M27** | Surfaces (MCP 2026-07-28, Codex/long-tail readers, CCA, detector/SIEM telemetry, Tier-2, Windows, gallery, cross-parser) | 42–47 | [Part 3](wbs-v0.2.0-part3-surfaces.md#milestone-m27--surfaces-prd-4247) |
| **M28** | Depth (Postgres, injection/memory, retention/signing, A2A/SYS/ACS/TS, governance) | 40–48 | [Part 4](wbs-v0.2.0-part4-depth-release.md#milestone-m28--depth-prd-4048) |
| **M29** | Field Tests (all v0.2.0 surfaces + CUJ-15–20 + test kit) | 40, 43, 47 | [Part 5](wbs-v0.2.0-part5-field-test-release.md#milestone-m29--field-tests-prd-40-43-47) |
| **M30** | Release Readiness (scan, audit, sign, all docs, merge to main, tag, publish PyPI/npm, verify) | 07, 09, 12, 40 | [Part 5](wbs-v0.2.0-part5-field-test-release.md#milestone-m30--release-readiness-prd-07-09-40) |

> **M29 (Field Tests) and M30 (Release Readiness) are always the last two milestones** — after the implementation
> milestones M25–M28. Do not tag `v0.2.0` before M30.
>
> **Progress:** 🚧 M25 (Foundations) in progress — **done:** SCHEMA-1 (#424), IDN-1 (#299), AAT-1/AAT-2
> (#295/#296), OTEL-1/OTEL-2 (#297/#298), TRACE-1 (#300), STR-1 (#301), DET-1 (#302), CUR-1/CUR-2
> (#303/#304), GEM-1 (#305), SDK-1..3 (#306–#308), XHT-1/XHT-4 (#309/#310), RSK-1 (#311), NAM-1 (#312,
> ADR-0026 decided), 25.T (#371), and the M25 tail CLI-1/CFG-1/CI-1 (#425–#427); FLD-1a plan drafted (#370).
> **Open:** 25.D (#372), 25.R (#373). Track status here and in each part file at milestone close.

## Track → ticket map

### Track A — Standards & interop ([PRD 41](../../prd/41-standards-and-interop-ii.md))
AAT-1 · AAT-2 · AAT-3 · AAT-4 · AAT-5 · OTEL-1 · OTEL-2 · OTEL-3 · OTEL-4 · TRACE-1 · TRACE-2 · PG-1 · PG-2 · PG-3 · SCHEMA-1

### Track B — Harness fidelity & real-time ([PRD 42](../../prd/42-harness-fidelity-and-realtime.md))
CUR-1 · CUR-2 · CUR-3 · GEM-1 · GEM-2 · COD-1 · MCP-1 · MCP-2 · MCP-3 · MCP-4 · MCP-5 · MCP-6 · STR-1 · STR-2 · STR-3 · LG-1 · LG-2 · UI-1 · RUN-1

### Track C — Detector credibility & evaluation ([PRD 43](../../prd/43-detector-credibility-and-evaluation.md))
DET-1 · DET-2 · DET-3 · DET-4 · DET-5 · DET-6 · DET-7 · COR-1 · COR-2 · COR-3 · COR-4

### Track D — Identity, enterprise & compliance ([PRD 44](../../prd/44-identity-enterprise-and-compliance.md))
IDN-1 · IDN-2 · IDN-3 · IDN-4 · CMP-1 · CMP-2 · CMP-3 · CMP-4 · SIEM-1 · SIEM-2 · UI-2

### Track E — New capture surfaces ([PRD 45](../../prd/45-new-capture-surfaces.md))
A2A-1 · A2A-2 · GWY-1 · GWY-2 · SYS-1 · CCA-1 · LOG-1 · ACS-1

### Track F — Platform, SDK & growth ([PRD 46](../../prd/46-platform-sdk-and-growth.md))
SDK-1 · SDK-2 · SDK-3 · WIN-1 · TSS-1 · API-1 · EXA-1 · FLD-1 · GOV-1 · CLI-1 · CFG-1 · DATA-1 · MIG-1 · TUT-1

### Track G — Cross-harness test kit ([PRD 47](../../prd/47-cross-harness-testkit.md))
XHT-1 · XHT-2 · XHT-3 · XHT-4

### Cross-cutting ([PRD 48](../../prd/48-v0.2.0-risks-testing-and-decisions.md))
NAM-1 (naming, [ADR-0026](../../adr/0026-naming-decision.md)) · RSK-1 (fuzz/property/mutation) · RSK-2 (threat model + ADRs) · SEC-1 (security baseline/traceability/attack matrix) · CI-1 (CI workflows) · PERF-1 (perf budgets) · A11Y-1 (accessibility) · TRC-1 (traceability + glossary)

## Per-milestone supporting tickets

Every milestone also carries three supporting tickets (in addition to its feature tickets):

- **`NN.T` — Add/expand test cases** (unit + integration + fault-injection for all new paths).
- **`NN.D` — Create/update the design + reference docs** (milestone doc list).
- **`NN.R` — Code review & risk sign-off** (per-PR review, guardrails, ADRs, threat rows, waivers recorded).

Milestone feature counts (excluding `NN.T/D/R`): M25 = 22 · M26 = 23 · M27 = 24 · M28 = 19 · M29 = 10 (field-test
work items; umbrella FLD-1) · M30 = 25 (release items).

## PRD coverage matrix (v0.2.0 docs 40–48 + edited 04/09)

| PRD | Topic | Milestone(s) |
|---|---|---|
| PRD 40 | v0.2.0 program (scope, gap register, cut-line, release gate) | cross-cutting |
| PRD 41 | Standards & Interop II (AAT-1..5, OTEL-1..4, TRACE-1..2, PG-1..3) | M25 (AAT-1/2, OTEL-1/2, TRACE-1), M26 (AAT-3..5, OTEL-3, TRACE-2), M28 (PG, OTEL-4) |
| PRD 42 | Harness Fidelity & Real-Time (CUR, GEM, COD, MCP, STR, LG) | M25 (CUR-1/2, GEM-1, STR-1), M26 (CUR-3, STR-2/3), M27 (MCP, COD, LOG, GEM-2, LG, WIN) |
| PRD 43 | Detector Credibility & Evaluation (DET, COR) | M25 (DET-1), M26 (DET-2/3, COR-1), M27 (DET-4/5, COR-2), M28 (DET-6/7, COR-3/4) |
| PRD 44 | Identity, Enterprise & Compliance (IDN, CMP, SIEM) | M25 (IDN-1), M26 (IDN-2/3, CMP-1/2), M27 (SIEM-1/2), M28 (IDN-4, CMP-3/4) |
| PRD 45 | New Capture Surfaces (A2A, GWY, SYS, CCA, LOG, ACS) | M26 (GWY), M27 (CCA, LOG), M28 (A2A, SYS, ACS) |
| PRD 46 | Platform, SDK & Growth (SDK, WIN, TSS, API, EXA, FLD, GOV) | M25 (SDK-1..3), M26 (API-1), M27 (WIN-1, EXA-1), M28 (TSS-1, GOV-1), M29 (FLD-1) |
| PRD 47 | Cross-Harness Test Kit (XHT) | M25 (XHT-1/4), M26 (XHT-2), M27 (XHT-3), M29 (validation) |
| PRD 48 | Risk, Testing & Decision Register | cross-cutting (RSK-1 M25, RSK-2 M26) |
| PRD 07 / 09 | Field tests + release readiness | M29, M30 |
| PRD 04 | CUJ-15..20 added | per owning PRD (see below) |
| PRD 09 | Roadmap (v0.2.0 scope) | — |

## CUJ → ticket map (PRD 04 additions)

| CUJ | Journey | Owning tickets | Milestone |
|---|---|---|---|
| CUJ-15 | "My auditor accepts my agent logs" | AAT-1..5 | M25–M26 |
| CUJ-16 | "Follow one action across agents and hosts" | TRACE-1..2, IDN-1..3 | M25–M26 |
| CUJ-17 | "Watch a live agent" | STR-1..3 | M25–M26 |
| CUJ-18 | "Prove compliance continuously" | CMP-1..4, SIEM-1..2 | M26–M28 |
| CUJ-19 | "Does this detector actually fire for us?" | DET-1..5, COR-1 | M25–M27 |
| CUJ-20 | "Who did my agent just delegate to?" | A2A-1..2, IDN-2 | M26–M28 |

## Requirements / capability detail

| Capability | Tickets | Milestone |
|---|---|---|
| Standards-native record (AAT) | AAT-1..5 | M25–M26 |
| OTel agent-span conformance + OTLP/gRPC | OTEL-1..4 | M25–M28 |
| Cross-agent/host trace correlation | TRACE-1..2 | M25–M26 |
| Real-time capture | STR-1..3 | M25–M26 |
| Real harness fidelity (Cursor/Gemini/Codex/long-tail) | CUR-1..3, GEM-1..2, COD-1, LOG-1 | M25–M27 |
| Full MCP surface (2026-07-28) | MCP-1..6 | M27 |
| Tier-2 frameworks (LangGraph/raw Python) | LG-1..2 | M27 |
| Detector credibility + public corpus | DET-1..5, COR-1 | M25–M27 |
| Injection + memory observations | DET-6..7 | M28 |
| Incident-registry interop | COR-2..4 | M27–M28 |
| Agent identity + delegation | IDN-1..4 | M25–M28 |
| Compliance reporting + retention + signing | CMP-1..4 | M26–M28 |
| SOC/SIEM feed (OCSF/Syslog) | SIEM-1..2 | M27 |
| New capture (A2A/gateway/system/compliance-API/ACS) | A2A-1..2, GWY-1..2, SYS-1, CCA-1, ACS-1 | M26–M28 |
| SDK lifecycle/sampler/provider | SDK-1..3 | M25 |
| Platform (Windows, API, examples) | WIN-1, API-1, EXA-1 | M26–M27 |
| Growth (TS spike, governance) | TSS-1, GOV-1 | M28 |
| Field tests (env + scripts + cases + report) | 29.1–29.10, FLD-1 | M29 |
| Release readiness (scan, audit, docs, merge, tag, publish, verify) | 30.1–30.25 | M30 |
| Test kit + honest fidelity tiers | XHT-1..4 | M25–M27 |
| Naming + risk/ADR register | NAM-1, RSK-1..2 | M25–M26 |
| Schema/spec/data-dictionary authoring | SCHEMA-1, DATA-1 | M25, M28 |
| CLI reference + error contract + launcher | CLI-1 | M25 |
| Config keys + `config explain` | CFG-1 | M25 |
| CI workflows for new jobs | CI-1 | M25 |
| Operator UI (live, identity/SIEM/detector) | UI-1, UI-2 | M26–M27 |
| Security baseline/traceability/attack matrix | SEC-1 | M26 |
| Performance budgets | PERF-1 | M26 |
| Accessibility for new views | A11Y-1 | M27 |
| Runbooks + tutorials | RUN-1, TUT-1 | M27 |
| Migration guide + traceability/glossary | MIG-1, TRC-1 | M28, M30 |

## ADRs (v0.2.0)

0016 AAT mapping · 0017 security-relevant sampling · 0018 streaming views vs store truth (+ trace propagation) ·
0019 derived Postgres index · 0020 agent identity dimension · 0021 Cursor capture contract · 0022 Gemini
native-telemetry ingest · 0023 MCP 2026-07-28 posture · 0024 foreign-data threat posture · 0025 A2A interposition ·
0026 naming decision (**required pre-launch**).

## Gap → milestone map (PRD 40 §1a)

| Gap | Owning tickets | Milestone |
|---|---|---|
| G1 batch polling | STR-1..3 | M25–M26 |
| G2 no distributed correlation | TRACE-1..2 | M25–M26 |
| G3 no multi-tenant | PG-2 | M28 (phaseable) |
| G4 silent detectors | DET-2..3 | M26 |
| G5 "modeled" adapters | CUR-1..3, GEM-1..2, COD-1, LOG-1, XHT-4 | M25–M27 |
| G6 MCP surface gaps | MCP-1..6 | M27 |
| G7 OTLP JSON only / semconv pin | OTEL-1..3 | M25–M26 |
| G8 signing not default | CMP-4 | M28 |
| G9 memory-audit / injection | DET-6..7 | M28 |
| G10 detector quality bar | DET-1..5 | M25–M27 |
| G11 no identity dimension | IDN-1..4 | M25–M28 |
| G12 no compliance report command | CMP-1..2 | M26 |

## Release gate

The eight criteria in [PRD 40](../../prd/40-v0.2.0-program.md) §5 (summarized): AAT third-party round-trip;
`known-limitations` shrink (G1/G2/G4/G7/G8 each leave with a proving test); no "modeled" Tier-1 rows; published
detector numbers with corpus + method; offline compliance report; streaming p99 ≤ 1 s; attribution end-to-end;
field-test report + claims ledger green + release notes/compatibility table/security audit.

## Policies

- **Cut-line** ([PRD 40](../../prd/40-v0.2.0-program.md) §1b): P0 set is in; cheap bundled items if capacity
  allows; PG-1..3 and the remaining surfaces phase to v0.2.x explicitly.
- **Definition of done** ([PRD 48](../../prd/48-v0.2.0-risks-testing-and-decisions.md) §5): conformance pack,
  claims-ledger entry, known-limitations line + proving test, threat-model line if trust-boundary, executable doc,
  matrix tier, field-test case.
- **Provenance:** [reference/v0.2.0-research-sources.md](../../reference/v0.2.0-research-sources.md).
