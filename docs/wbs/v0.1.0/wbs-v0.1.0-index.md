# WBS — agentwatch v0.1.0 (Index)

**BLUF:** v0.1.0 delivers P0 requirements R1–R8 for Claude Code, monitor-only, local-first, with the
security-event schema defined and replay working. **Porting from the shipped `agent-exec-trace` project is
frontloaded** — we reuse its code rather than rewrite. Six milestones (M0–M5), split across three detail
files (max 2 milestones per file).

## Standard milestone exit criteria (applies to EVERY milestone)

- [ ] **All tests pass** (`make test`)
- [ ] **Code coverage ≥ 95%** (enforced in CI)
- [ ] **Lint strict clean** — `ruff` zero violations; `mypy --strict` clean
- [ ] **Design docs updated** (milestone-specific list in each file)
- [ ] **Port tasks complete** (each milestone frontloads its `agent-exec-trace` port)

## Milestones

| M | Name | Port (frontloaded) | Detail file |
|---|---|---|---|
| **M0** | Foundation | monorepo layout, tooling, Makefile, quality gates | [Part 1](wbs-v0.1.0-part1-foundation-schema.md#milestone-m0--foundation) |
| **M1** | Record + security-event schema | record/trace schema + models | [Part 1](wbs-v0.1.0-part1-foundation-schema.md#milestone-m1--record-format--security-event-schema) |
| **M2** | Claude Code adapter + daemon | instrumentation SDK (spans, LangGraph, OTLP) | [Part 2](wbs-v0.1.0-part2-recording.md#milestone-m2--claude-code-adapter--daemon) |
| **M3** | Local store + redaction | privacy modes / redaction | [Part 2](wbs-v0.1.0-part2-recording.md#milestone-m3--local-store--redaction) |
| **M4** | OTel export + replay | OTLP export, replay/timeline concepts | [Part 3](wbs-v0.1.0-part3-export-release.md#milestone-m4--otel-export--replay) |
| **M5** | First-run + release | CI, field-test, release tooling | [Part 3](wbs-v0.1.0-part3-export-release.md#milestone-m5--first-run--release) |

## Porting map (agent-exec-trace → agentwatch)

Source: https://github.com/agentsec-ecosystem/agent-exec-trace (archived, MIT).
Process: copy module → rename namespace (`agent_exec_trace` → `agentwatch`) → adapt imports → run its tests →
keep or re-derive per PRD 10.

| Shipped artifact | Ported at | Notes |
|---|---|---|
| Monorepo layout, `pyproject.toml`, `Makefile`, quality gates | **M0** | frontloaded |
| Record/trace schema + models | **M1** | extend with the security-event schema |
| Instrumentation SDK — spans, LangGraph adapter, OTLP, metadata | **M2** | rename namespace; privacy modes kept |
| Privacy modes / redaction | **M3** | retained; add secret/PII classes |
| OTLP export orchestrator | **M4** | retained |
| Replay / run-timeline concepts | **M4** | retained |
| CI, field-test harness, release tooling | **M5** | retained |
| Analytics pipeline, 40 detectors, FastAPI read API, React UI, local stack | **v0.2.0–v1.0** | per [PRD 09](../../prd/09-roadmap.md); parity gate at v1.0 |

> **Rule:** in each milestone, port first (frontload), then adapt/add. Any ported module that changes behavior
> updates its design doc in the same milestone.

## Requirements → milestone

| Req | Milestone(s) |
|---|---|
| R1 record every tool call | M1 (format), M2 (capture), M3 (store) |
| R2 zero code changes, ≤15 min | M2 (hooks), M5 (first-run gate) |
| R3 Claude Code coverage | M2 |
| R4 OTel GenAI export | M4 |
| R5 security-event schema | M1, M3 |
| R6 local-first | M3 |
| R7 redaction-by-default | M3 |
| R8 session replay | M4 |

Full mapping: [PRD 12 — Traceability](../../prd/12-traceability.md) · Review log: [codereview-log.md](codereview-log.md).
