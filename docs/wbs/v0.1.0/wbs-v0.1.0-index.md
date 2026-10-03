# WBS — agentwatch v0.1.0 (Index)

**BLUF:** **v0.1.0 delivers the entire PRD scope** — port `agent-exec-trace` first (M0), add the security
layer, then the full feature set (R1–R13, parity A1–A6, NFR-1..12, F1–F10, compliance) plus the reviewed
additions (R14–R25, PRD 19–30: lifecycle, delivery guarantees, operator tooling, capture fidelity, platform
strategy). Sixteen milestones (M0–M15), split across eight detail files (max 2 milestones per file). The
additions fold into M5–M13; **M14 (Field Tests) and M15 (Release Readiness) remain the last two.**

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
| M14 | Field Tests | [Part 8](wbs-v0.1.0-part8-field-test-release.md#milestone-m14--field-tests) |
| M15 | Release Readiness + predecessor retention | [Part 8](wbs-v0.1.0-part8-field-test-release.md#milestone-m15--release-readiness) |

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
> **M7 (Read API + operator UI) ✅** — ported FastAPI read API (42 tests) and React/Vite operator UI
> verified, plus `agentwatch view` (#195) and `agentwatch explain` (#211).
>
> **M8 (Local stack + demo/seed + E2E) 🚧 partial** — ported compose stack, demo agent, seed/replay,
> and Playwright E2E specs verified; plus transcript import (#192), `diff` (#193), `search` (#194),
> `tail --alert` (#196), golden corpus (#199), and investigation cookbook (#205). **Reopened:** #69
> (field-test harness runner) and #63 (a11y automated checks).

## Porting map (agent-exec-trace → agentwatch)

Source: https://github.com/agentsec-ecosystem/agent-exec-trace (MIT; archived, made private and retained). The port is a **bulk move**
(M0); later milestones adapt and add. Namespace rename `agent_exec_trace` → `agentwatch`.

| Shipped artifact | Ported at |
|---|---|
| Entire repo tree (`packages/`, `services/`, `apps/`, `deploy/`, `examples/`, `tests/`, `schema`, tooling) | **M0** |
| CLI/packaging metadata; record/trace schema; instrumentation SDK; privacy/redaction; OTLP export + replay | M1–M5 |
| Analytics pipeline + 40 detectors; FastAPI read API + React UI | M6–M7 |
| Docker Compose stack, demo, seed/replay, Playwright E2E, field-test harness | M8 |
| CI + release tooling | M13 |

> **Predecessor retention:** once **M0** lands (code fully represented, tests green), agentwatch is
> self-contained; `agent-exec-trace` is **made private and retained at M13 — never deleted**.
>
> **M0 execution:** [m0-port-execution-plan.md](../../plans/m0-port-execution-plan.md).

## PRD coverage matrix (every doc 00–18)

| PRD | Topic | Milestone(s) |
|---|---|---|
| **PRD 00** | Press Release / FAQ | context/narrative; validated at M13 |
| **PRD 01** | Why | context (all milestones) |
| **PRD 02** | Architecture | M0–M5 |
| **PRD 03** | Landscape / migration / retain predecessor (private) | M0, M13 |
| **PRD 04** | Users & CUJs (CUJ-1..7) | M3, M5, M4, M9, M7, M11 |
| **PRD 05** | Features R1–R13 | M2–M11 |
| **PRD 06** | Security baseline / tamper | M4, M12 |
| **PRD 07** | Success metrics / release gate | M12, M14, M15 |
| **PRD 08** | Risks (product + build) | cross-cutting; M12 |
| **PRD 09** | Roadmap | M15 |
| **PRD 10** | Feature parity A1–A6 + gate | M0–M8; gate M15 |
| **PRD 11** | Decisions DD-01..DD-15 | cross-cutting (honored every milestone) |
| **PRD 12** | Traceability (maintained) | every milestone |
| **PRD 13** | NFR-1..NFR-12 + self-observability | M12 (a11y also M7) |
| **PRD 14** | Non-goals (scope guard) | every milestone |
| **PRD 15** | Data model + lifecycle | M2, M4 |
| **PRD 16** | Configuration | M1 |
| **PRD 17** | Error handling F1–F10 | M12 (per-milestone fault tests too) |
| **PRD 18** | Compliance (OWASP/NIST/ISO/SOC2/OpenSSF) | M13, M15 |
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
