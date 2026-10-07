# WBS — agentwatch v0.2.0 (Index)

**BLUF:** **v0.2.0 turns the shipped record layer into the best-in-class one** (PRD 40–48, extended by PRD 49–59). Ten
work tracks plus per-milestone supporting tickets, across **eight milestones (M25–M32)**, every ticket with an owner
PRD, a deliverable, an acceptance seed, an issue number, and a fidelity/honesty gate. This index is the ticket source;
the seven part files carry the milestone-level detail (Goal · Requirements · Work-item tables · Tests · Evidence ·
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
| **M29** | **Expanded I — Trust, Identity & Governance** (authorization/oversight, deployability + attestation, harness-native telemetry + frameworks, access/governance, legal hold, OWASP Agentic) | 49–51, 56, 59 | [Part 5](wbs-v0.2.0-part5-expanded-trust-identity-governance.md#milestone-m29--expanded-i-trust-identity--governance-prd-4951-56-59) |
| **M30** | **Expanded II — Code, Capabilities, Console & Investigation** (capability supply chain + memory, code provenance, local console + query tier, agent interfaces, policy-from-history, investigation depth, outcomes, ephemeral capture) | 52–55, 57–58 | [Part 6](wbs-v0.2.0-part6-expanded-code-capabilities-console.md#milestone-m30--expanded-ii-code-capabilities-console--investigation-prd-5255-5758) |
| **M31** | Field Tests (all v0.2.0 + expanded surfaces + CUJ-15–34 + test kit) | 40, 43, 47 | [Part 7](wbs-v0.2.0-part7-field-test-release.md#milestone-m31--field-tests-prd-40-43-47) |
| **M32** | Release Readiness (scan, audit, sign, all docs, merge to main, tag, publish PyPI/npm, verify) | 07, 09, 12, 40 | [Part 7](wbs-v0.2.0-part7-field-test-release.md#milestone-m32--release-readiness-prd-07-09-40) |

> **M31 (Field Tests) and M32 (Release Readiness) are always the last two milestones** — after the implementation
> milestones M25–M30. Do not tag `v0.2.0` before M32.
>
> **Milestone reorder (2026-10-05):** the expanded milestones **M29/M30** were inserted before field/release; the
> former field/release **M29/M30 → M31/M32**. Their scope is unchanged (extended with the expanded cases). On GitHub,
> the field/release issues move to the new milestone numbers (**M29-issues → M31, M30-issues → M32**); the new
> expanded tickets are filed onto **M29/M30**.
>
> **Progress:** ✅ **M25 (Foundations) complete** (2026-10-05) — SCHEMA-1 (#424), IDN-1 (#299), AAT-1/AAT-2
> (#295/#296), OTEL-1/OTEL-2 (#297/#298), TRACE-1 (#300), STR-1 (#301), DET-1 (#302), CUR-1/CUR-2
> (#303/#304), GEM-1 (#305), SDK-1..3 (#306–#308), XHT-1/XHT-4 (#309/#310), RSK-1 (#311), NAM-1 (#312,
> ADR-0026 decided), 25.T (#371), 25.D (#372), 25.R (#373, signed off), and the M25 tail CLI-1/CFG-1/CI-1
> (#425–#427); FLD-1a plan drafted (#370). Accepted gap: CUR-1 live-install capture deferred. Track status here
> and in each part file at milestone close.
>
> **Progress:** ✅ **M26 (Interop & Proofs) complete** (2026-10-06) — AAT-3..5 (#313–#315), OTEL-3 (#316),
> TRACE-2 (#317), CUR-3 (#318), STR-2 (#319), STR-3 (#320), DET-2 (#321), DET-3 (#322), COR-1 (#323),
> IDN-2 (#324), IDN-3 (#325), CMP-1 (#326), CMP-2 (#327), GWY-1 (#328), GWY-2 (#329), API-1 (#330), RSK-2 (#332),
> SEC-1 (#429), PERF-1 (#430), and 26.T/D/R (#374/#375/#376, signed off). Gates at HEAD (`6939678`): `make test`
> green (SDK 1627 passed/95.15%, API 46/96.80%, analytics 724/95.15%, repo guard 34), `ruff` clean,
> `mypy --strict` clean. **Re-pointed (blocked, declared):** UI-1 → M30 (console), XHT-2 → M31 (field tests).
> Milestone closed 2026-10-06.
>
> **Progress:** ✅ **M27 (Surfaces) complete** (2026-10-06) — 26 feature/support tickets done (MCP-1..6, GEM-2,
> DET-4, DET-5, COR-2, SIEM-1/2, LG-1, LG-2, EXA-1, COD-1, XHT-3, LOG-1, CCA-1, UI-2, A11Y-1, RUN-1, TUT-1,
> 27.T, 27.D); **WIN-1 declared and re-pointed to M31 field tests** (service unit + `windows-latest` leg landed;
> named-pipe transport + CUJ-1 Windows timing). Gate green (`make test`: SDK 95.02%/1735, API 95.75%/53,
> analytics 95.18%/728, repo guard 34; ruff/mypy/web clean). 27.R signed off (maintainer, 2026-10-06).

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

### Track H — Expanded: trust, identity, governance, code & capabilities (PRD 49–59)
APV-1 · APV-2 · APV-3 · DEP-1 · DEP-2 · DEP-3 · CCO-1 · CCO-2 · FWK-1 · FWK-2 · ACC-1 · ACC-2 · HLD-1 · ASI-1 · STD-1 ·
CAP-1 · CAP-2 · CAP-3 · MEM-1 · PRV-1 · PRV-2 · PRV-3 · LUI-1 · LUI-2 · AGI-1 · AGI-2 · POL-1 · POL-2 · RED-1 ·
ENV-1 · IR-1 · CNC-1 · VFY-1 · SBX-1 · OUT-1 · OUT-2 · RUN-1 · DEMO-1 · NTF-1

### Cross-cutting ([PRD 48](../../prd/48-v0.2.0-risks-testing-and-decisions.md))
NAM-1 (naming, [ADR-0026](../../adr/0026-naming-decision.md)) · RSK-1 (fuzz/property/mutation) · RSK-2 (threat model + ADRs) · SEC-1 (security baseline/traceability/attack matrix) · CI-1 (CI workflows) · PERF-1 (perf budgets) · A11Y-1 (accessibility) · TRC-1 (traceability + glossary)

## Per-milestone supporting tickets

Every milestone also carries three supporting tickets (in addition to its feature tickets):

- **`NN.T` — Add/expand test cases** (unit + integration + fault-injection for all new paths).
- **`NN.D` — Create/update the design + reference docs** (milestone doc list).
- **`NN.R` — Code review & risk sign-off** (per-PR review, guardrails, ADRs, threat rows, waivers recorded).

Milestone feature counts (excluding `NN.T/D/R`): M25 = 22 · M26 = 23 · M27 = 24 · M28 = 19 · **M29 = 17 (expanded I)** ·
**M30 = 29 (expanded II)** · M31 = 14 (field-test work items; umbrella FLD-1) · M32 = 27 (release items).

## PRD coverage matrix (v0.2.0 docs 40–48 + expanded 49–59 + edited 04/09)

| PRD | Topic | Milestone(s) |
|---|---|---|
| PRD 40 | v0.2.0 program (scope, gap register, cut-line, release gate) | cross-cutting |
| PRD 41 | Standards & Interop II (AAT-1..5, OTEL-1..4, TRACE-1..2, PG-1..3) | M25 (AAT-1/2, OTEL-1/2, TRACE-1), M26 (AAT-3..5, OTEL-3, TRACE-2), M28 (PG, OTEL-4) |
| PRD 42 | Harness Fidelity & Real-Time (CUR, GEM, COD, MCP, STR, LG) | M25 (CUR-1/2, GEM-1, STR-1), M26 (CUR-3, STR-2/3), M27 (MCP, COD, LOG, GEM-2, LG, WIN) |
| PRD 43 | Detector Credibility & Evaluation (DET, COR) | M25 (DET-1), M26 (DET-2/3, COR-1), M27 (DET-4/5, COR-2), M28 (DET-6/7, COR-3/4) |
| PRD 44 | Identity, Enterprise & Compliance (IDN, CMP, SIEM) | M25 (IDN-1), M26 (IDN-2/3, CMP-1/2), M27 (SIEM-1/2), M28 (IDN-4, CMP-3/4) |
| PRD 45 | New Capture Surfaces (A2A, GWY, SYS, CCA, LOG, ACS) | M26 (GWY), M27 (CCA, LOG), M28 (A2A, SYS, ACS) |
| PRD 46 | Platform, SDK & Growth (SDK, WIN, TSS, API, EXA, FLD, GOV) | M25 (SDK-1..3), M26 (API-1), M27 (WIN-1, EXA-1), M28 (TSS-1, GOV-1), M31 (FLD-1) |
| PRD 47 | Cross-Harness Test Kit (XHT) | M25 (XHT-1/4), M26 (XHT-2), M27 (XHT-3), M31 (validation) |
| PRD 48 | Risk, Testing & Decision Register | cross-cutting (RSK-1 M25, RSK-2 M26, decisions §6) |
| PRD 07 / 09 | Field tests + release readiness | M31, M32 |
| PRD 04 | CUJ-15..34 added | per owning PRD (see below) |
| PRD 09 | Roadmap (v0.2.0 scope) | — |
| **PRD 49** | Authorization & Oversight (APV) | M29 |
| **PRD 50** | Deployability & Recorder Attestation (DEP) | M29 |
| **PRD 51** | Harness-Native Telemetry & Framework Reach (CCO, FWK) | M29 |
| **PRD 52** | Capability Supply Chain & Memory (CAP, MEM) | M30 |
| **PRD 53** | Code Provenance & Attribution (PRV) | M30 |
| **PRD 54** | Local Console & Query Tier (LUI) | M30 |
| **PRD 55** | Agent Interfaces & Policy-from-History (AGI, POL) | M30 |
| **PRD 56** | Governance, Retention Integrity & Redaction Quality (ACC, HLD, RED) | M29 (ACC, HLD), M30 (RED) |
| **PRD 57** | Investigation Depth & Evidence Verification (ENV, IR, CNC, VFY, SBX) | M30 |
| **PRD 58** | Outcomes, Ephemeral Capture & Growth (OUT, RUN, DEMO, NTF) | M30 |
| **PRD 59** | OWASP Agentic & Standards Coverage (ASI, STD) | M29 |

## CUJ → ticket map (PRD 04 additions)

| CUJ | Journey | Owning tickets | Milestone |
|---|---|---|---|
| CUJ-15 | "My auditor accepts my agent logs" | AAT-1..5 | M25–M26 |
| CUJ-16 | "Follow one action across agents and hosts" | TRACE-1..2, IDN-1..3 | M25–M26 |
| CUJ-17 | "Watch a live agent" | STR-1..3 | M25–M26 |
| CUJ-18 | "Prove compliance continuously" | CMP-1..4, SIEM-1..2, ASI-1 | M26–M29 |
| CUJ-19 | "Does this detector actually fire for us?" | DET-1..5, COR-1, RED-1 | M25–M30 |
| CUJ-20 | "Who did my agent just delegate to?" | A2A-1..2, IDN-2 | M26–M28 |
| CUJ-21 | "Was a human actually in the loop?" | APV-1..3, CCO-1 | M29 |
| CUJ-22 | "Which commit did the agent write?" | PRV-1..3 | M30 |
| CUJ-23 | "Did a skill/plugin/rules file change?" | CAP-1..3, MEM-1 | M30 |
| CUJ-24 | "Browser view in 60 s, no Docker" | LUI-1..2 | M30 |
| CUJ-25 | "Roll out under managed settings" | DEP-1..3 | M29 |
| CUJ-26 | "Let an agent query the record safely" | AGI-1..2 | M30 |
| CUJ-27 | "Turn history into a tighter policy" | POL-1..2 | M30 |
| CUJ-28 | "Instrument my agent in two lines" | FWK-1..2, CCO-2 | M29 |
| CUJ-29 | "Cost versus what stuck" | OUT-1..2 | M30 |
| CUJ-30 | "Unattended runner evidence" | RUN-1 | M30 |
| CUJ-31 | "Roll out recording lawfully/transparently" | ACC-1..2 | M29 |
| CUJ-32 | "Legal hold for this case" | HLD-1 | M29 |
| CUJ-33 | "It worked last week — what changed?" | ENV-1 | M30 |
| CUJ-34 | "Package this incident (many sessions)" | IR-1 | M30 |

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
| **Authorization + oversight provenance** | APV-1..3 | M29 |
| **Deployability + recorder attestation** | DEP-1..3 | M29 |
| **Harness-native telemetry + framework reach** | CCO-1..2, FWK-1..2 | M29 |
| **Fleet access & governance + legal hold** | ACC-1..2, HLD-1 | M29 |
| **OWASP Agentic coverage + standards participation** | ASI-1, STD-1 | M29 |
| **Capability supply chain + memory** | CAP-1..3, MEM-1 | M30 |
| **Code provenance + Agent Trace** | PRV-1..3 | M30 |
| **Local console + embedded query tier** | LUI-1..2 | M30 |
| **Agent interfaces + policy-from-history** | AGI-1..2, POL-1..2 | M30 |
| **Investigation depth + evidence verification** | ENV-1, IR-1, CNC-1, VFY-1, SBX-1 | M30 |
| **Outcomes + ephemeral capture + growth** | OUT-1..2, RUN-1, DEMO-1, NTF-1 | M30 |
| **Redaction benchmark** | RED-1 | M30 |
| Field tests (env + scripts + cases + report) | M31.1–31.14, FLD-1 | M31 |
| Release readiness (scan, audit, docs, merge, tag, publish, verify) | 32.1–32.27 | M32 |
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
| Migration guide + traceability/glossary | MIG-1, TRC-1 | M28, M32 |

## ADRs (v0.2.0 + expanded)

**v0.2.0 (40–48):** 0016 AAT mapping · 0017 security-relevant sampling · 0018 streaming views vs store truth (+ trace
propagation) · 0019 derived Postgres index · 0020 agent identity dimension · 0021 Cursor capture contract · 0022 Gemini
native-telemetry ingest · 0023 MCP 2026-07-28 posture · 0024 foreign-data threat posture · 0025 A2A interposition ·
0026 naming decision (**required pre-launch**).

**Expanded (49–59):** 0027 authorization taxonomy v2 · 0028 managed-policy install · 0029 recorder attestation ·
0030 hook transport/budget · 0031 native-telemetry join · 0032 capability inventory scope · 0033 range+hash capture ·
0034 Agent Trace pin · 0035 embedded index tier · 0036 console security · 0037 MCP read-only server · 0038 policy
suggestion boundary · 0039 runner segment custody · 0040 fleet role model · 0041 legal hold · 0042 environment
fingerprint · 0043 memory capability · 0044 browser verifier · 0045 standards participation.

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
| G9 memory-audit / injection | DET-6..7, MEM-1 | M28–M30 |
| G10 detector quality bar | DET-1..5, RED-1 | M25–M30 |
| G11 no identity dimension | IDN-1..4, APV-1..3 | M25–M29 |
| G12 no compliance report command | CMP-1..2, ASI-1 | M26–M29 |
| G13 stale approval / oversight | APV-1..3 | M29 |
| G14 silent recorder / no attestation / hook cost | DEP-1..3 | M29 |
| G15 home-harness telemetry not ingested | CCO-1..2 | M29 |
| G16 capability supply chain invisible | CAP-1..3, MEM-1 | M30 |
| G17 no code provenance | PRV-1..3 | M30 |
| G18 browser UI needs Docker | LUI-1..2 | M30 |
| G19 no agent-facing interface | AGI-1..2 | M30 |
| G20 no policy-from-history | POL-1..2 | M30 |
| G21 OWASP Agentic not mapped / DD-05 open | ASI-1, STD-1 | M29 |
| G22 environment changes not diffed | ENV-1 | M30 |
| G23 hold/privacy/redaction gaps | ACC-1..2, HLD-1, RED-1 | M29–M30 |
| G24 ephemeral agents / investigation / verifier / sandbox | RUN-1, IR-1, CNC-1, VFY-1, SBX-1 | M30 |

## Release gate

The eight criteria in [PRD 40](../../prd/40-v0.2.0-program.md) §5 (summarized): AAT third-party round-trip;
`known-limitations` shrink (G1/G2/G4/G7/G8 each leave with a proving test); no "modeled" Tier-1 rows; published
detector numbers with corpus + method; offline compliance report; streaming p99 ≤ 1 s; attribution end-to-end;
field-test report + claims ledger green + release notes/compatibility table/security audit.

**Expanded additions (items 9–16):** clean-OS timing (3 OSes); two OTel backends; no auto/bypass recorded as `user`;
`ui` from a clean install with no Docker; managed-policy install verified or declared; Plugin4Shell-shape drift
detected + commit→session + Agent Trace validates; `suggest-policy`/`what-if` write nothing outside `--out` +
`owasp-asi-2026` every row runs; held records survive retention/purge/rebuild.

## Policies

- **Cut-line** ([PRD 40](../../prd/40-v0.2.0-program.md) §1b): P0 set is in (incl. expanded APV/DEP/CCO/CAP/PRV/LUI/ASI/
  ENV/VFY/HLD/ACC); cheap bundled items if capacity allows; PG-1..3 (re-sequenced behind LUI-2) and the remaining
  surfaces phase to v0.2.x explicitly.
- **Definition of done** ([PRD 48](../../prd/48-v0.2.0-risks-testing-and-decisions.md) §5): conformance pack,
  claims-ledger entry, known-limitations line + proving test, threat-model line if trust-boundary, executable doc,
  matrix tier, field-test case.
- **Expanded execution plan:** [plans/v0.2.0-expanded-execution-plan.md](../../plans/v0.2.0-expanded-execution-plan.md).
- **Provenance:** [reference/v0.2.0-research-sources.md](../../reference/v0.2.0-research-sources.md) (§1–§10 PRD 40–48;
  §11–§19 PRD 49–59).
