# WBS — agentwatch v0.1.0 (Index)

**BLUF:** **v0.1.0 delivers the entire PRD scope** — port `agent-exec-trace` first (M0), add the security
layer, then the full feature set (R1–R13, parity A1–A6, NFRs, resilience, compliance). Fourteen milestones
(M0–M13), split across seven detail files (max 2 milestones per file).

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
| M13 | Compliance + full-parity release + decommission (PRD 18, 07, 09) | [Part 7](wbs-v0.1.0-part7-hardening-release.md#milestone-m13--compliance--full-parity-release--decommission) |

## Porting map (agent-exec-trace → agentwatch)

Source: https://github.com/agentsec-ecosystem/agent-exec-trace (archived, MIT). The port is a **bulk move**
(M0); later milestones adapt and add. Namespace rename `agent_exec_trace` → `agentwatch`.

| Shipped artifact | Ported at |
|---|---|
| Entire repo tree (`packages/`, `services/`, `apps/`, `deploy/`, `examples/`, `tests/`, `schema`, tooling) | **M0** |
| CLI/packaging metadata; record/trace schema; instrumentation SDK; privacy/redaction; OTLP export + replay | M1–M5 |
| Analytics pipeline + 40 detectors; FastAPI read API + React UI | M6–M7 |
| Docker Compose stack, demo, seed/replay, Playwright E2E, field-test harness | M8 |
| Detection of new capabilities (inventory, harness adapters, fleet) builds on the port | M9–M11 |
| CI + release tooling | M13 |

> **Decommission:** once **M0** lands (code fully represented, tests green), `agent-exec-trace` is redundant
> and is **deleted at M13**.

## PRD → WBS coverage matrix

Every PRD item maps to a milestone (nothing is unimplemented).

| PRD / item | Milestone(s) |
|---|---|
| 02 Architecture | M0–M5 |
| 03 Landscape / migration | M0, M13 |
| 04 CUJ-1 install+record; CUJ-2 replay; CUJ-3 export; CUJ-4 event | M3; M5; M5; M4 |
| 04 CUJ-5 inventory; CUJ-6 version compare; CUJ-7 drift | M9; M7; M11 |
| 05 R1 record; R2 ≤15min; R3 Claude Code; R4 OTel export; R5 event schema; R6 local-first; R7 redaction; R8 replay | M2/M3/M4; M3/M13; M3; M5; M2/M4; M4; M4; M5 |
| 05 R9 inventory; R10 harness/framework expansion; R11 retention; R12 viewer; R13 fleet | M9; M10; M9; M7; M11 |
| 06 Security baseline / tamper | M4, M12 |
| 07 Success metrics / release gate | M12, M13 |
| 08 Risks (product + build) | cross-cutting; M12 |
| 09 Roadmap | M13 |
| 10 Feature parity A1–A6 + gate | M0–M8; gate M13 |
| 11 Decisions DD-01..DD-15 | cross-cutting |
| 12 Traceability (maintained) | every milestone |
| 13 NFR-1..NFR-12 + self-observability | M12 (a11y at M7) |
| 14 Non-goals (scope guard) | every milestone |
| 15 Data model + lifecycle | M2, M4 |
| 16 Configuration | M1 |
| 17 Error handling F1–F10 | M12 (per-milestone fault tests too) |
| 18 Compliance (OWASP/NIST/OpenSSF) | M13 |
| Design docs / schema / reference | updated every milestone |

Full requirement→test mapping: [PRD 12](../../prd/12-traceability.md) · Review log: [codereview-log.md](codereview-log.md).
