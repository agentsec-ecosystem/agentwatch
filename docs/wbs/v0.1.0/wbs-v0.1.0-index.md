# WBS — agentwatch v0.1.0 (Index)

**BLUF:** **v0.1.0 delivers the entire PRD scope** — port `agent-exec-trace` first (M0), add the security
layer, then the full feature set (R1–R13, parity A1–A6, NFR-1..12, F1–F10, compliance) plus the reviewed
additions (R14–R25, PRD 19–30: lifecycle, delivery guarantees, operator tooling, capture fidelity, platform
strategy) **and the new additions (PRDs 31–39: evidence, coverage/trust, investigation, forensics, capture
context, interop, config, engineering rigor, compliance acceptance)**. Twenty-five milestones (M0–M24), split
across thirteen detail files (max 2 milestones per file). The additions fold into M5–M13 and **M14–M22**;
**M23 (Field Tests) ✅ complete; M24 (Release Readiness) 🔄 in progress — 24.1–24.8 done (`v0.1.0` tagged
2026-10-04); predecessor privacy (24.9) remains.**

## Standard milestone exit criteria (applies to EVERY milestone)

- [ ] **All tests pass** (`make test`)
- [ ] **Code coverage ≥ 95%** (enforced in CI)
- [ ] **Lint strict clean** — `ruff` zero violations; `mypy --strict` clean
- [ ] **Design docs updated** (milestone-specific list in each file)
- [ ] **Port tasks complete** (each milestone frontloads its `agent-exec-trace` port)

## Milestones

| M | Name | Detail file |
|---|---|---|
| **M0** | **Port the entire codebase** (urgent) | [Part 1](wbs-v0.1.0-part1-port-foundation.md#milestone-m0--port-the-entire-codebase) |
| M1 | Foundation & identity | [Part 1](wbs-v0.1.0-part1-port-foundation.md#milestone-m1--foundation--identity) |
| M2 | Record + security-event schema | [Part 2](wbs-v0.1.0-part2-schema-adapter.md#milestone-m2--record--security-event-schema) |
| M3 | Claude Code adapter + daemon | [Part 2](wbs-v0.1.0-part2-schema-adapter.md#milestone-m3--claude-code-adapter--daemon) |
| M4 | Local store + redaction | [Part 3](wbs-v0.1.0-part3-store-export.md#milestone-m4--local-store--redaction) |
| M5 | OTel export + replay | [Part 3](wbs-v0.1.0-part3-store-export.md#milestone-m5--otel-export--replay) |
| M6 | Analytics + detector engine | [Part 4](wbs-v0.1.0-part4-analytics-ui.md#milestone-m6--analytics--detector-engine) |
| M7 | Read API + operator UI | [Part 4](wbs-v0.1.0-part4-analytics-ui.md#milestone-m7--read-api--operator-ui) |
| M8 | Local stack + demo/seed + E2E | [Part 5](wbs-v0.1.0-part5-stack-inventory.md#milestone-m8--local-stack--demoseed--e2e) |
| M9 | Inventory + retention (R9, R11) | [Part 5](wbs-v0.1.0-part5-stack-inventory.md#milestone-m9--inventory--retention-r9-r11) |
| M10 | Harness + framework expansion (R10) | [Part 6](wbs-v0.1.0-part6-expansion.md#milestone-m10--harness--framework-expansion-r10) |
| M11 | Fleet aggregation (R13) + drift signals | [Part 6](wbs-v0.1.0-part6-expansion.md#milestone-m11--fleet-aggregation-r13--drift-signals) |
| M12 | NFRs + resilience + error handling (PRD 13, 17) | [Part 7](wbs-v0.1.0-part7-hardening-release.md#milestone-m12--nfrs--resilience--error-handling) |
| M13 | Compliance + full-parity release + predecessor retention (PRD 18, 07, 09) | [Part 7](wbs-v0.1.0-part7-hardening-release.md#milestone-m13--compliance--full-parity-release--predecessor-retention) |
| M14 | Engineering Rigor (Q1–Q13) | [Part 9](wbs-v0.1.0-part9-rigor-and-evidence.md) |
| M15 | Evidence & Provenance (PRD 31) | [Part 9](wbs-v0.1.0-part9-rigor-and-evidence.md) |
| M16 | Coverage & Recorder Trust (PRD 32) | [Part 10](wbs-v0.1.0-part10-trust-and-investigation.md) |
| M17 | Investigation & Impact (PRD 33) | [Part 10](wbs-v0.1.0-part10-trust-and-investigation.md) |
| M18 | Content-Flow Forensics (PRD 34) | [Part 11](wbs-v0.1.0-part11-forensics-and-context.md) |
| M19 | Capture Context (PRD 35) | [Part 11](wbs-v0.1.0-part11-forensics-and-context.md) |
| M20 | Standards & Interop (PRD 36) | [Part 12](wbs-v0.1.0-part12-interop-and-config.md) |
| M21 | Configuration, Profiles & Capture Hygiene (PRD 37) | [Part 12](wbs-v0.1.0-part12-interop-and-config.md) |
| M22 | Standards & Compliance Acceptance (PRD 39) | [Part 13](wbs-v0.1.0-part13-compliance-acceptance.md) |
| M23 | Field Tests | [Part 8](wbs-v0.1.0-part8-field-test-release.md#milestone-m23--field-tests) |
| M24 | Release Readiness + predecessor retention | [Part 8](wbs-v0.1.0-part8-field-test-release.md#milestone-m24--release-readiness) |

> **Progress:** ✅ M0 (port), ✅ M1 (foundation & identity), ✅ M2 (record + security-event schema), and
> ✅ M3 (Claude Code adapter + daemon — `agentwatch init`/`uninstall`, `sessions`, `status` reporting; #159
> closed). M1 execution:
> [m1-foundation-execution-plan.md](../../plans/m1-foundation-execution-plan.md) · M2/M3 execution:
> [m2-m3-schema-adapter-execution-plan.md](../../plans/m2-m3-schema-adapter-execution-plan.md).
>
> **M4 (Local store + redaction) ✅** — hash-chained store, secret/PII redaction, `verify-store`,
> retention/F3/F4, export self-test. Execution plan:
> [m4-store-redaction-execution-plan.md](../../plans/m4-store-redaction-execution-plan.md).
>
> **M5 (OTel export + replay) 🚧** — additions **P1–P5 ✅ complete** (lifecycle #165–#169, delivery
> #172/#173/#182/#183/#217, M4 minors #181, format #185, export/replay #39–#46/#123/#124/#184,
> observability/tooling #170/#175/#176/#188/#190/#191/#197, ecosystem/conformance #171/#216).
>
> **M6 (Analytics + detector engine) ✅** — ported analytics service verified (706 tests), plus
> `tool.response` (#198) and the Claude Code detector pack (#210).
>
> **M7 (Read API + operator UI) ✅** — ported FastAPI read API (42 tests) and React/Vite
> operator UI; plus `agentwatch view` (#195), `agentwatch explain` (#211), and automated axe a11y
> checks for all five views (#63, `apps/web/src/__tests__/a11y.test.tsx`).
>
> **M8 (Local stack + demo/seed + E2E) ✅** — ported compose stack, demo agent, seed/replay,
> and Playwright E2E specs verified; plus transcript import (#192), `diff` (#193), `search` (#194),
> `tail --alert` (#196), golden corpus (#199), and investigation cookbook (#205). **8.5** (field-test
> harness) is folded into M23 23.1 (#141) as a single Playwright harness that drives the stack.
>
> **M9 (Inventory + retention) ✅** — `agentwatch inventory` (agents + MCP servers, `mcp__` attribution),
> capture fidelity (`project` / `prompt_version` / `parent_session_id`, `--project` filters), and
> `retention apply` / `purge` (tombstone + marker; chain stays green).
>
> **M10 (Harness + framework expansion) ✅ complete** — all five phases landed: Phase 1 (adapter plugin
> contract: `agentwatch.protocol` + published store-format / daemon-protocol / adapter-api specs + sample
> community adapter + pack check), Phase 2 (provisional modeled Cursor / Codex CLI / Gemini CLI), Phase 3
> (MCP proxy: adapter, stdio relay, daemon `phase: "mcp"`, HTTP/SSE, `init --mcp-proxy` install + byte-exact
> restore), Phase 4 (provisional modeled **Tier-2** CrewAI / PydanticAI), Phase 5 (**OTel/NDJSON
> ingestion** `agentwatch ingest`, deterministic **fake-harness emitters**, and a **generated compatibility
> table + nightly version-drift matrix**).
>
> **Checkpoint (2026-10-03, M10 phases 4–5 — M10 complete):** commits `6101de6` (Tier-2 adapters),
> `b924e73` (OTel/NDJSON ingestion), `2ef1e19` (fake-harness emitters), `1932bf8` (generated compatibility
> table + drift matrix), and the docs commit deliver WBS **10.6 / 10.N2 / 10.N3 / 10.N4** and close **#84,
> #213, #214, #215** (with **#86/#133/#134**). Gates at HEAD: SDK tests + coverage ≥95%, `ruff` clean,
> `mypy --strict` clean, repo guard green. Plans:
> [m10-phases-4-5-plan.md](../../plans/m10-phases-4-5-plan.md); design:
> [harness-adapter-design.md](../../design/harness-adapter-design.md).
>
> **M11 (Fleet aggregation + drift signals) ✅ complete** — implemented local-first in the SDK:
> `host` record tag + a new `drift-detected` security event (additive schema), `agentwatch.fleet`
> (multi-host ingestion + rollups, `agentwatch fleet`), and `agentwatch.drift` (trailing-baseline
> signals — never fixed thresholds — emitted as events, plus deployment correlation, `agentwatch drift`).
> Commits `afa1b97` (schema), `39df718` (fleet), `3e76b0f` (drift), and the docs commit; closes
> **#87–#92** (with **#135/#136**). Plan: [m11-fleet-drift-plan.md](../../plans/m11-fleet-drift-plan.md).
>
> **M12 (NFRs + resilience + error handling) ✅ complete** — store hardening (`agentwatch.posture`
> 0700/0600, `store.durability` modes, chain checkpoints, continuous verify, `verify-store --repair`),
> clock-skew flagging (F9), rotated daemon logs, `init --service`, the perf harness/budget (NFR-1),
> sizing, fault-injection F1–F10, i18n/UTC, and offline/soak CI jobs. Plan:
> [m12-nfrs-resilience-plan.md](../../plans/m12-nfrs-resilience-plan.md).
>
> **M13 (Compliance + full-parity release + predecessor retention) ✅ complete.** Release tooling
> (SBOM/checksums/Sigstore provenance via `release.yml`), first-run evidence, self-audit, OWASP/NIST/ISO/SOC2
> compliance matrix, the executable A1–A6 parity gate, versioning/backwards-compat validation, and
> replay-as-code (#204). **Environment/timing items moved to their natural milestones:** first-run timing →
> **M24 24.2**, field-test execution → **M23 23.2**, tag → **M24 24.8**, predecessor privacy → **M24 24.9**.
> **M23 (Field Tests) ✅ complete** — 50/50 field-test cases, 226/226 detector scenarios across 43
> detectors, 49/49 Playwright; four defects fixed with regression evidence; `FIELD_TEST_REPORT.md`
> published (issues #141–#147, #104, #279–#285).
> **M24 (Release Readiness) 🔄 in progress** — 24.1–24.8 done: security scan, SBOM/signing dry-run,
> compliance matrix + OpenSSF checklist, versioning, release notes + compatibility table, README, and
> **`v0.1.0` tagged** (PyPI trusted publishing wired into `release.yml`). Remaining: **24.9
> `agent-exec-trace` private**.
>
> **M14 (Engineering Rigor, Q1–Q13) ✅ complete** — property/differential/mutation/fuzz testing, whole-repo
> CI, enforced perf budget, conformance vectors, forward-compat matrix, machine-readable error contract,
> claims ledger, executable docs, WCAG 2.2 AA, time correctness, and the signing release pipeline
> (issues #218–#230).
>
> **M15 (Evidence & Provenance, PRD 31) ✅ complete** — the `producer` provenance field (S26 #234),
> `agentwatch annotate` (S20 #236), `store-access` read auditing (S21 #235), redaction receipts +
> `redact --preview` (S32 #237), `agentwatch bom` CycloneDX (S9 #233), the offline `agentwatch evidence`
> bundle (S1 #231), and the standalone `agentwatch-verify` zipapp + published reference (S12 #232).
> Plan: [m15-evidence-provenance-plan.md](../../plans/m15-evidence-provenance-plan.md).
>
> **M16 (Coverage & Recorder Trust, PRD 32) ✅ complete** — `agentwatch coverage` reconciles the store
> against transcript ground truth and classifies every gap (S2 #238), recorder-state audit records +
> coverage windows (S5 #239), the harness-drift canary from live traffic (S19 #240), quarantine operator
> tooling (S27 #241), sealed/archived chain segments (S28 #243), and the anti-forensics suite +
> published recorder attack matrix (S30 #242). Plan:
> [m16-coverage-recorder-trust-plan.md](../../plans/m16-coverage-recorder-trust-plan.md).
>
> **M17 (Investigation & Impact, PRD 33) ✅ complete** — the shared deterministic argument classifier +
> `agentwatch impact` (S3 #244), file-centric `agentwatch blame` (S18 #246), the `bd1:` behavior
> fingerprint + `sessions --group-by-behavior` (S7 #249), local `agentwatch cost` with a versioned
> pricing table (S6 #252), the subagent `agentwatch tree` (S17 #245), the cross-session `agentwatch at`
> window (S24 #247), denied-then-retried sequences in replay/impact/evidence (S25 #248), session
> end-state derivation (`interrupted-by-user`/`errored`/`abandoned`) (S33 #250), and the local
> `agentwatch digest` (S37 #251). Plan:
> [m17-investigation-impact-plan.md](../../plans/m17-investigation-impact-plan.md).
>
> **M18 (Content-Flow Forensics, PRD 34) ✅ complete** — keyed-HMAC `content-flow` edges for untrusted
> content that reappears as an argument (S22 #253) and exposed-secret tracing across a session
> (S23 #254), both metadata-only (`agentwatch flow`, `agentwatch secrets`). Plan:
> [m18-content-flow-forensics-plan.md](../../plans/m18-content-flow-forensics-plan.md).
>
> **M19 (Capture Context, PRD 35) ✅ complete** — approval provenance (`user | auto | not-required |
> denied | unknown`, S14 #255), context-compaction boundaries (S15 #256), the session-start VCS
> revision (S16 #257) and OS principal (S29 #258) snapshot, and `agentwatch demo` proving the pipeline
> (S31 #259). Plan: [m19-capture-context-plan.md](../../plans/m19-capture-context-plan.md).
>
> **M20 (Standards & Interop, PRD 36) ✅ complete** — OCSF + CloudEvents mappings for the security-event
> schema (S8 #260), a reference consumer under `examples/` (S38 #261), a thin OTel collector component
> (S39 #262), opt-in rule-free file/webhook/syslog event sinks (S10 #263), and MCP `tool-surface-changed`
> drift (S4 #264). Plan: [m20-standards-interop-plan.md](../../plans/m20-standards-interop-plan.md).
>
> **M21 (Configuration, Profiles & Capture Hygiene, PRD 37) ✅ complete** — `agentwatch config explain`
> (S34 #265), install profiles (S35 #266), the visible pathological-record guard (S36 #267), the
> read-time SDK/hook union (S11 #268), and the standalone redactor + filter (S13 #269). Plan:
> [m21-config-hygiene-plan.md](../../plans/m21-config-hygiene-plan.md).
>
> **M22 (Standards & Compliance Acceptance, PRD 39) ✅ complete** — EU AI Act (W1 #270) and ISO/NIST
> appendices (W2 #271), open artifact standards pinned (W3 #272), the OTel GenAI semconv pin + drift
> check (W4 #273), enforceable schema stewardship (W5 #274), a forensic-soundness statement shipped in
> bundles (W6 #275), `checkpoint export` notarization (W7 #276), OpenSSF/OSV readiness (W8 #277), and
> optional signed checkpoints (W9 #278). Plan:
> [m22-compliance-acceptance-plan.md](../../plans/m22-compliance-acceptance-plan.md).

## Remaining (as of 2026-10-03)

**Blocking open issues (milestones reopened):** none — M7, M8, and M9 are complete.

**Deferred to M23 (Field Tests):** M8 **8.5** field-test harness → **23.1 (#141)** — delivered as a
single **Playwright** harness that drives the Docker/compose + seed + E2E setup.

**Known limitation:** real authenticated golden-corpus capture (#199) remains deferred; the committed
corpus is synthesized-from-shape (per D-19.39) and the real-corpus test skips with a reason.

**Resolved since the last audit:** **M7 (#63)** — automated axe a11y checks now run in the UI test
suite for all five views (`apps/web/src/__tests__/a11y.test.tsx`); milestone 8 complete. **M8 8.5**
folded into M23 23.1. **M14 and M15** are complete (see above).

**Not started:** none of the M5–M23 implementation milestones. **M24 (Release Readiness) 🔄 in progress** —
24.1–24.8 done (release tag cut); predecessor privacy (**24.9**) remains.
**M23 (Field Tests) ✅ complete. M24 (Release Readiness) 🔄 in progress — `v0.1.0` tagged; predecessor privacy (24.9) remains.**

**Unverified (environment):** `docker compose up` health, `make seed-e2e` load, and Playwright
**green** were not run — the Docker daemon was unavailable; the E2E specs are ported and validated but
not executed end-to-end.

**Verified at the MCP proxy Plan A checkpoint:** SDK **630 passed** (+1 skipped); MCP proxy modules 99–100%
coverage. Prior audit (unchanged this session): analytics 706; API 42; docs link-check 5; demo-agent 12;
web vitest 4; Playwright 34 cases discovered.

## Porting map (agent-exec-trace → agentwatch)

Source: https://github.com/agentsec-ecosystem/agent-exec-trace (MIT; archived, made private and retained). The port is a **bulk move**
(M0); later milestones adapt and add. Namespace rename `agent_exec_trace` → `agentwatch`.

| Shipped artifact | Ported at |
|---|---|
| Entire repo tree (`packages/`, `services/`, `apps/`, `deploy/`, `examples/`, `tests/`, `schema`, tooling) | **M0** |
| CLI/packaging metadata; record/trace schema; instrumentation SDK; privacy/redaction; OTLP export + replay | M1–M5 |
| Analytics pipeline + 40 detectors; FastAPI read API + React UI | M6–M7 |
| Docker Compose stack, demo, seed/replay, Playwright E2E | M8 |
| Field-test harness (single Playwright harness, drives the stack) | M23 |
| PRD 31–39 additions (evidence, coverage/trust, investigation, forensics, capture context, interop, config, rigor, compliance acceptance) | M14–M22 |
| CI + release tooling | M13 |

> **Predecessor retention:** once **M0** lands (code fully represented, tests green), agentwatch is
> self-contained; `agent-exec-trace` is **made private and retained at M13 — never deleted**.
>
> **M0 execution:** [m0-port-execution-plan.md](../../plans/m0-port-execution-plan.md).

## PRD coverage matrix (every doc 00–39)

| PRD | Topic | Milestone(s) |
|---|---|---|
| **PRD 00** | Press Release / FAQ | context/narrative; validated at M24 |
| **PRD 01** | Why | context (all milestones) |
| **PRD 02** | Architecture | M0–M5 |
| **PRD 03** | Landscape / migration / retain predecessor (private) | M0, M13 |
| **PRD 04** | Users & CUJs (CUJ-1..7) | M3, M5, M4, M9, M7, M11 |
| **PRD 04** | Additions (CUJ-8..14) | M14–M23 |
| **PRD 05** | Features R1–R13 | M2–M11 |
| **PRD 06** | Security baseline / tamper | M4, M12 |
| **PRD 07** | Success metrics / release gate | M12, M23, M24 |
| **PRD 08** | Risks (product + build) | cross-cutting; M12 |
| **PRD 09** | Roadmap | M24 |
| **PRD 10** | Feature parity A1–A6 + gate | M0–M8; gate M24 |
| **PRD 11** | Decisions DD-01..DD-15 | cross-cutting (honored every milestone) |
| **PRD 12** | Traceability (maintained) | every milestone |
| **PRD 13** | NFR-1..NFR-12 + self-observability | M12 (a11y also M7) |
| **PRD 14** | Non-goals (scope guard) | every milestone |
| **PRD 15** | Data model + lifecycle | M2, M4 |
| **PRD 16** | Configuration | M1 |
| **PRD 17** | Error handling F1–F10 | M12 (per-milestone fault tests too) |
| **PRD 18** | Compliance (OWASP/NIST/ISO/SOC2/OpenSSF) | M13, M24 |
| **PRD 19** | Agent lifecycle coverage (R14) | M5 |
| **PRD 20** | Usage & cost accounting (R15) | M5–M6 |
| **PRD 21** | Data integrity & delivery guarantees (R18) | M5, M12 |
| **PRD 22** | Recorder self-observability (R16) | M5, M12 |
| **PRD 23** | Ecosystem event interchange (R17, R22) | M5, M10, M13 |
| **PRD 24** | Operator trust & consent (R19) | M5 |
| **PRD 25** | Capture fidelity & data model (R21) | M6–M9 |
| **PRD 26** | Query & investigation experience (R20) | M7–M9 |
| **PRD 27** | Harness expansion & conformance (R22, R23) | M5, M8, M10 |
| **PRD 28** | Performance & operability (R24) | M5, M12 |
| **PRD 29** | LLM explanation layer (R25) | M7 (stretch) |
| **PRD 30** | Analytics signals | M6 |
| **PRD 31** | Evidence & provenance (S1, S12, S9, S26, S21, S20, S32) | M15 |
| **PRD 32** | Coverage & recorder trust (S2, S5, S19, S27, S30, S28) | M16 |
| **PRD 33** | Investigation & impact (S3, S17, S18, S24, S25, S7, S33, S37, S6) | M17 |
| **PRD 34** | Content-flow forensics (S22, S23) | M18 |
| **PRD 35** | Capture context (S14, S15, S16, S29, S31) | M19 |
| **PRD 36** | Standards & interop (S8, S38, S39, S10, S4) | M20 |
| **PRD 37** | Configuration, profiles & capture hygiene (S34, S35, S36, S11, S13) | M21 |
| **PRD 38** | Engineering rigor (Q1–Q13) | M14 |
| **PRD 39** | Standards & compliance acceptance (W1–W9) | M22 |
| Design docs / schema / reference | updated every milestone |

## Requirements detail (R1–R13, R14–R25)

| Req | Milestone(s) |
|---|---|
| R1 record every tool call | M2, M3, M4 |
| R2 zero code changes, ≤15 min | M3, M13 |
| R3 Claude Code coverage | M3 |
| R4 OTel GenAI export | M5 |
| R5 security-event schema | M2, M4 |
| R6 local-first | M4 |
| R7 redaction-by-default | M4 |
| R8 session replay | M5 |
| R9 shadow-agent / MCP inventory | M9 |
| R10 harness / framework expansion | M10 |
| R11 retention + hash-chaining | M9 |
| R12 local replay viewer | M7 |
| R13 fleet aggregation | M11 |

**Additions (PRD 19–30, R14–R25):**

| Req | Milestone(s) |
|---|---|
| R14 lifecycle completeness (session boundaries, denied, prompts, subagents) | M5 |
| R15 usage & cost accounting (tokens, model) | M5–M6 |
| R16 self-observability `/healthz` | M5, M12 |
| R17 ecosystem event ingestion | M5 |
| R18 delivery guarantees (spool, dedup, gaps, quarantine, cursor, format version) | M5, M12 |
| R19 operator tooling (doctor, verify-privacy, consent init, preflight, CLI polish) | M5 |
| R20 query & investigation (import, diff, search, view, alerts, cookbook) | M7–M9 |
| R21 capture fidelity (tool responses, golden corpus) | M6–M9 |
| R22 platform plumbing (contract, conformance runner, session export, compatibility matrix) | M5, M8, M10, M13 |
| R23 harness expansion horizontals (MCP interposition, OTel ingestion) | M10 |
| R24 performance honesty (async hooks, durability, offline proof, service units, soak) | M5, M12 |
| R25 LLM explanation layer (local-first) | M7 (stretch) |

## NFRs (PRD 13) → M12

| NFR | Milestone |
|---|---|
| NFR-1 ≤5 ms/step | M12 |
| NFR-2 ingestion latency | M6, M12 |
| NFR-3 storage growth / retention | M9, M12 |
| NFR-4 first-run ≤15 min | M3, M13 |
| NFR-5 footprint | M12 |
| NFR-6 portability (macOS/Linux) | M12 |
| NFR-7 scale | M11, M12 |
| NFR-8 fail-closed | M12 |
| NFR-9 privacy / no egress | M4 |
| NFR-10 accessibility | M7, M12 |
| NFR-11 coverage ≥95% / quality gates | every milestone |
| NFR-12 self-observability (`/healthz`) | M12 |

## Error handling (PRD 17) → M12

| Failure | Milestone |
|---|---|
| F1 daemon crash · F2 hook fail · F3 store full · F4 chain corrupt · F5 export fail | M12 (with M3/M4/M5 fault tests) |
| F6 self-test fail · F7 bad config · F8 normalize error · F9 clock skew · F10 partial session | M12 (F7 also M1) |

## Parity (PRD 10) → shipped

| Row | Milestone(s) |
|---|---|
| A1 instrumentation SDK | M0–M3 |
| A2 40 detectors | M6 |
| A3 analytics pipeline | M6 |
| A4 read API | M7 |
| A5 operator UI | M7 |
| A6 stack / demo / E2E / field test | M8, M13 |

## CUJs (PRD 04)

CUJ-1 install+record → M3 · CUJ-2 replay → M5 · CUJ-3 export → M5 · CUJ-4 event → M4 ·
CUJ-5 inventory → M9 · CUJ-6 version compare → M7 · CUJ-7 drift → M11.

## Decisions (PRD 11)

DD-01..DD-15 are honored across milestones (e.g., DD-01 Python core → all; DD-06 redact-before-store → M4;
DD-08 JSONL store → M4; DD-09 export gating → M5; DD-12 API compat → M7/M13; DD-13 license → M0/M13).

Full requirement→test mapping: [PRD 12 — Traceability](../../prd/12-traceability.md) · Review log: [codereview-log.md](codereview-log.md).
