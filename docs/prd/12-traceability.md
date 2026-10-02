# PRD 12 — Requirements Traceability Matrix

**BLUF:** Every v0.1.0 requirement ties to a user journey, a WBS part, an acceptance test, and (where
applicable) a shipped-feature **parity row**. Nothing is orphaned.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## v0.1.0 requirements

| Req | CUJ | WBS part | Acceptance test | Parity row |
|---|---|---|---|---|
| R1 record every tool call | CUJ-1 | 2, 3, 4 | session timeline reconstructs from store | A1 (behavior trace schema) |
| R2 zero code changes, ≤15 min | CUJ-1 | 8 | fresh-machine install, first call recorded | A1 (SDK path) |
| R3 Claude Code coverage | CUJ-1 | 3 | Pre/PostToolUse captured; gaps documented | extra (coding agents) |
| R4 OTel GenAI export | CUJ-3 | 6 | loads into ≥2 standard backends unmodified | A1 (OTLP) |
| R5 security-event schema | CUJ-4 | 2 | fixture events validate against schema; ≥1 sibling emits | extra |
| R6 local-first storage | CUJ-1 | 4 | core works with no network | A1 (local store) |
| R7 redaction-by-default | CUJ-1 | 5 | attack pack finds zero secrets in store | A1 (4 privacy modes) |
| R8 session replay | CUJ-2 | 7 | replay matches raw transcript (automated) | A1 (run timeline) |

## Parity rows (agent-exec-trace shipped → PRD 10 matrix A)

| Parity row | Agentwatch version | Verification |
|---|---|---|
| A1 instrumentation SDK (spans, LangGraph, OTLP, privacy modes, metadata) | v0.2.0 | SDK conformance tests |
| A2 40 detectors (35 rule + 5 LLM) | v0.3.0 | detector unit + corpus tests |
| A3 analytics pipeline (rollups, cohorts) | v0.2.0 | pipeline tests |
| A4 read API (`/runs`, `/fleet`, `/compare`, `/anomalies`) | v0.2.0 | API contract tests |
| A5 operator UI (Fleet, Timeline, Compare, Inbox, Agent Detail) | v0.3.0–v1.0 | E2E Playwright |
| A6 stack/tooling/field-test | v0.2.0–v1.0 | CI + field test |

## Rule

A requirement or parity row without a linked acceptance test is not "done". The v1.0 parity gate re-checks
**every** matrix-A row.
