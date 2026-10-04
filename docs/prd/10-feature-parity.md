# PRD 10 — Feature Parity (Shipped-Feature Superset)

**BLUF:** agentwatch **replaces the shipped project `agent-exec-trace` / AgentObservatory (#102)**. Parity
is **mandatory and in-repo**: every feature that **shipped** in that project must be delivered **by
agentwatch itself** — not delegated to a sibling tool and not waived. Parity is scoped to **what actually
shipped** (its `v0.1.0` release, 2026-08-05), not to its planned-but-unreleased milestones.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## Parity rule (non-negotiable)

1. Every capability in the shipped `agent-exec-trace` release is **Delivered by agentwatch** — see matrix A.
   No row may be *Delegated* or *Waived*.
2. **Release gate:** agentwatch **v0.1.0** cannot ship until every matrix-A row is delivered **and tested**
   here.
3. Bonus/additive features (matrix B/C) must never regress parity.

## A. Shipped in agent-exec-trace v0.1.0 (+ unreleased fixes) — binding, in agentwatch

Source: the project's `CHANGELOG.md` and `README.md` (archived, read-only; retained as a private repo).

### A1. Instrumentation SDK (Python, PyPI `agent-exec-trace`)
| Shipped capability | In agentwatch |
|---|---|
| Raw Python decorator `@trace_agent` + context managers `plan_span`, `tool_span`, `retrieval_span`, `memory_span`, `approval_span` | ✅ required |
| LangGraph adapter (`TracedGraph`, node-level instrumentation) | ✅ required |
| Direct OTLP export via `AgentTracer` | ✅ required |
| Four privacy modes — Metadata-only (default), Truncated, Hashed, Full | ✅ required |
| Version/workload metadata propagation (`agent_name`, `agent_version`, `workload_type`) + optional `prompt_version`, `model_version`, `tool_schema_version` | ✅ required |
| Async-first instrumentation (incl. the async `@trace_agent` fix) | ✅ required |

### A2. Detectors
| Shipped capability | In agentwatch |
|---|---|
| **35 rule-based detectors** across 7 categories: Tool Execution (8), Cost & Resource (6), Runtime & Completion (5), Retry & Recovery (5), Interaction & Control (4), Output Quality (4), Cross-Run Patterns (3) | ✅ required |
| **5 optional LLM-augmented detectors** (feature-flagged, default off): SemanticLoop, Hallucination, GoalDrift, QualityDegradation, ConfusionPattern | ✅ required |
| Structured anomaly records with severity, explanation, and evidence payloads; configurable thresholds per detector per workload | ✅ required |

### A3. Analytics pipeline
| Shipped capability | In agentwatch |
|---|---|
| Jaeger polling for trace ingestion (configurable fetch limit) | ✅ required |
| Run summary materialization into Postgres | ✅ required |
| Fleet rollup + version cohort summaries | ✅ required |

### A4. Read API (FastAPI)
| Shipped endpoint | In agentwatch |
|---|---|
| `/api/runs`, `/api/runs/{id}`, `/api/fleet`, `/api/compare`, `/api/anomalies` | ✅ required |

### A5. Web UI (React)
| Shipped view | In agentwatch |
|---|---|
| Fleet Health (agent cohorts, run/anomaly counts, filters) | ✅ required |
| Run Timeline (span tree, anomaly badges, metadata) | ✅ required |
| Version Compare (side-by-side deltas: cost, retry rate, success rate, tool usage) | ✅ required |
| Anomaly Inbox (triage by severity/type/agent) | ✅ required |
| Agent Detail (per-agent metrics, tool mix, cost trend, anomaly history) | ✅ required |

### A6. Stack, tooling, and evidence
| Shipped capability | In agentwatch |
|---|---|
| Local-first stack: Jaeger/Tempo + OTel Collector + Postgres + API + Analytics + Web (Docker Compose, 6 services) | ✅ required |
| Monorepo layout (`packages/`, `services/`, `apps/`, `deploy/`, `examples/`, `tests/`) | ✅ required |
| `Makefile` targets (setup, lint, typecheck, test, stack-up/down, seed-e2e, migrate) | ✅ required |
| Quality gates: ruff zero, mypy strict, tests green, coverage ≥95% | ✅ required |
| Demo agent (LangGraph `request-triage`, deterministic normal/loop/high-cost paths) | ✅ required |
| Seed/replay workflow (96 runs, ~240 anomalies, 4 agents) | ✅ required |
| E2E Playwright tests (Fleet Health, Run Timeline, Version Compare, Anomaly Inbox) | ✅ required |
| Field-test harness + reports (100K-trace HF corpus, synthetic corpus, compatibility audit) | ✅ required |
| Four privacy modes + anomaly evidence payloads | ✅ required |

## B. Extra — beyond the superseded project (agentwatch's additions)

Not present in agent-exec-trace; these are why agentwatch exists:

- **Open security-event schema** (`denied`, `policy-fired`, `secret-detected`, `revoked`, `halted`).
- **Coding-agent harness coverage** — Claude Code hooks first, then Cursor/Codex/Gemini (the shipped
  project only instrumented frameworks/raw Python).
- **Security posture** — redaction-by-default generalized, local-first, hash-chained tamper-evident store,
  fail-closed on tamper.
- **OTel GenAI semconv** implementation + W3C Trace Context.
- **MCP server / shadow-agent inventory.**

## C. Not shipped → non-binding

- **AgentWatch (#66)** was never shipped; its ideas (per-step metrics, trailing-baseline drift, deployment
  correlation, Slack alerts) are **bonus**, not parity.
- **agent-exec-trace planned but unshipped** items are **not** parity: no policy-overlay view, no memory
  audit UI, no multi-agent interaction maps, no PydanticAI adapter. (Its own "Known Issues" list confirms
  these did not ship.)
- Known shipped **limitations** we may improve but are not required to replicate: batch polling (~30s delay),
  no distributed trace correlation, no multi-tenant isolation, LLM detectors research-grade, 28/35
  detectors silent on the HF corpus.

## D. Compatibility & migration (must preserve)

- Existing `agent-exec-trace` users instrument with `@trace_agent` / `TracedGraph` and read the FastAPI
  surface. Parity implies **the instrumentation API and the read API shape remain compatible** (or ship a
  documented migration), so existing integrations do not break.
- The PyPI package distribution and the four privacy modes are part of the contract.
- **Port-first:** the entire codebase is ported in WBS **M0**; once its tests are green in CI,
  `agent-exec-trace` is **made private and retained** (WBS M13).

## E. Decision — resolved

**Accepted (2026-10-02): keep the Python core for true parity.** agentwatch preserves a Python-compatible
core (instrumentation SDK + analytics service + FastAPI) and the shipped instrumentation/read-API
contracts. `npx @agentsec-ecosystem/cli` remains a thin launcher that installs/invokes the Python CLI; the
Python CLI is also published on PyPI. See `DD-01` in `../design/design-decisions.md`.
