# WBS — agentwatch v0.1.0 (Index)

**BLUF:** **Port the entire `agent-exec-trace` codebase FIRST (M0)** so the old repo becomes redundant and
can be deleted. Then adapt it into agentwatch and add the security layer. **v0.1.0 delivers the complete
shipped-feature superset** (parity + extras). Ten milestones (M0–M9), split across five detail files
(max 2 milestones per file).

## Standard milestone exit criteria (applies to EVERY milestone)

- [ ] **All tests pass** (`make test`)
- [ ] **Code coverage ≥ 95%** (enforced in CI)
- [ ] **Lint strict clean** — `ruff` zero violations; `mypy --strict` clean
- [ ] **Design docs updated** (milestone-specific list in each file)
- [ ] **Port tasks complete** (each milestone frontloads its `agent-exec-trace` port)

## Milestones

| M | Name | Port (frontloaded) | Detail file |
|---|---|---|---|
| **M0** | **Port the entire codebase** (urgent) | **everything**: packages, services, apps, deploy, examples, tests, schema, tooling | [Part 1](wbs-v0.1.0-part1-port-foundation.md#milestone-m0--port-the-entire-codebase) |
| **M1** | Foundation & identity | Makefile/pyproject gates, CLI pattern | [Part 1](wbs-v0.1.0-part1-port-foundation.md#milestone-m1--foundation--identity) |
| **M2** | Record + security-event schema | record/trace schema + models | [Part 2](wbs-v0.1.0-part2-schema-adapter.md#milestone-m2--record--security-event-schema) |
| **M3** | Claude Code adapter + daemon | instrumentation SDK (spans, LangGraph, OTLP) | [Part 2](wbs-v0.1.0-part2-schema-adapter.md#milestone-m3--claude-code-adapter--daemon) |
| **M4** | Local store + redaction | privacy modes / redaction | [Part 3](wbs-v0.1.0-part3-store-export.md#milestone-m4--local-store--redaction) |
| **M5** | OTel export + replay | OTLP export, replay/timeline | [Part 3](wbs-v0.1.0-part3-store-export.md#milestone-m5--otel-export--replay) |
| **M6** | Analytics + detector engine | analytics service, 40 detectors | [Part 4](wbs-v0.1.0-part4-analytics-ui.md#milestone-m6--analytics--detector-engine) |
| **M7** | Read API + operator UI | FastAPI read API, React UI (5 views) | [Part 4](wbs-v0.1.0-part4-analytics-ui.md#milestone-m7--read-api--operator-ui) |
| **M8** | Local stack + demo/seed + E2E | Docker Compose stack, demo, seed, Playwright | [Part 5](wbs-v0.1.0-part5-stack-release.md#milestone-m8--local-stack--demoseed--e2e) |
| **M9** | Full-parity release + decommission | CI, field-test harness, release tooling | [Part 5](wbs-v0.1.0-part5-stack-release.md#milestone-m9--full-parity-release--decommission) |

## Porting map (agent-exec-trace → agentwatch)

Source: https://github.com/agentsec-ecosystem/agent-exec-trace (archived, MIT). The port is a **bulk move**
(M0); later milestones adapt and add. Process: copy → rename namespace `agent_exec_trace` → `agentwatch` →
adapt imports → run the ported tests.

| Shipped artifact | Ported at |
|---|---|
| **Entire repo tree** — `packages/`, `services/`, `apps/`, `deploy/`, `examples/`, `tests/`, `schema`, `Makefile`, `pyproject.toml`, docs | **M0** |
| CLI install pattern, packaging metadata | M1 |
| Record/trace schema + models | M2 |
| Instrumentation SDK — spans, LangGraph, OTLP, metadata | M3 |
| Privacy modes / redaction | M4 |
| OTLP export orchestrator, replay/run-timeline | M5 |
| Analytics pipeline (polling, summaries, rollups, cohorts) + 40 detectors | M6 |
| FastAPI read API + React operator UI (5 views) | M7 |
| Docker Compose stack, demo agent, seed/replay, Playwright E2E, field-test harness | M8 |
| CI, release tooling | M9 |

> **Decommission:** once **M0** lands (code fully represented in agentwatch and its tests green), the
> `agent-exec-trace` repository is redundant and can be **deleted** — it is already archived. Confirmed
> deletion at M9 after the ported suite is green in CI.

## Requirements → milestone

| Req | Milestone(s) |
|---|---|
| R1 record every tool call | M2, M3, M4 |
| R2 zero code changes, ≤15 min | M3, M9 |
| R3 Claude Code coverage | M3 |
| R4 OTel GenAI export | M5 |
| R5 security-event schema | M2, M4 |
| R6 local-first | M4 |
| R7 redaction-by-default | M4 |
| R8 session replay | M5 |
| Parity A2/A3 (analytics, detectors) | M6 |
| Parity A4/A5 (API, UI) | M7 |
| Parity A6 (stack, demo, E2E, field test) | M8 |

Full mapping: [PRD 12](../../prd/12-traceability.md) · Review log: [codereview-log.md](codereview-log.md).
