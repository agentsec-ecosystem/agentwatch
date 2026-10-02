# PRD 05 — What (Features)

**BLUF:** agentwatch is the **shipped-feature superset** of `agent-exec-trace` (the project it replaces).
v0.1.0 is the foundation — record every Claude Code tool call, redacted by default, OTel GenAI format,
local store, replay, security-event schema. Later versions restore **every capability that shipped in
agent-exec-trace** — the Python instrumentation SDK, the 40-detector analytics engine, the FastAPI read
API, the React operator UI, and the local stack — plus agentwatch's security additions.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## v0.1.0 scope

One harness (**Claude Code**), monitor-only by default, zero agent-side code changes, ≤15-minute setup.

## P0 — Must have (v0.1.0)

| # | Requirement | Acceptance criterion |
|---|---|---|
| **R1** | Record every tool call — tool name, arguments **redacted by default**, outcome, agent identity, session | A Claude Code session's full action timeline is reconstructable from the record |
| **R2** | Zero code changes to the agent/harness to start recording | Fresh machine → first recorded tool call in ≤15 min for Claude Code |
| **R3** | Harness coverage — Claude Code at v0.1.0 | Native Pre/PostToolUse surface met; unsupported classes documented honestly |
| **R4** | Export the standard open telemetry format for GenAI/agent traces | Data loads into at least two common backends unmodified |
| **R5** | Define **and emit** the open security-event schema (`denied`, `policy-fired`, `secret-detected`, `revoked`, `halted`) | Schema published; events emitted by ≥1 other ecosystem tool |
| **R6** | Local-first storage; data leaves the machine only if export is configured | No network required for core function |
| **R7** | Redaction-by-default — no secrets/PII in stored arguments | Verification attack pack finds zero leaks in stored records |
| **R8** | Session replay — given a session id, produce the ordered action timeline | Replay matches the raw transcript in an automated test |

## Feature parity — everything that shipped returns to agentwatch (required)

Per [PRD 10](10-feature-parity.md), every capability that **shipped** in `agent-exec-trace` v0.1.0 is
delivered **in agentwatch** (never delegated). Sequence:

| Version | Shipped capability restored to agentwatch |
|---|---|
| **v0.1.0** | Foundation: coding-agent recording (Claude Code), OTel GenAI export, **security-event schema**, redaction-by-default + local-first store, session replay |
| **v0.2.0** | **Instrumentation SDK** — `@trace_agent` + `plan/tool/retrieval/memory/approval` spans, LangGraph adapter, `AgentTracer` OTLP export, **4 privacy modes** (metadata-only/truncated/hashed/full), version/workload metadata; **analytics pipeline** — trace polling, run summaries, fleet rollup, version cohorts, configurable detector thresholds; **read API** — `/runs`, `/runs/{id}`, `/fleet`, `/anomalies`; demo agent + seed/replay; local stack (Docker Compose); quality gates |
| **v0.3.0** | **40 detectors** — 35 rule-based across 7 categories + 5 LLM-augmented (feature-flagged); **Run Timeline**, **Fleet Health**, **Anomaly Inbox** UI; retention controls + hash-chaining |
| **v1.0** | **Version Compare** + **Agent Detail** UI; **all shipped features tested** → the parity release gate |

> **Bonus (not binding):** **AgentWatch (#66)** was never shipped; its ideas (per-step metrics, trailing
> baselines, deployment correlation, Slack alerts) are additive, delivered if/when built.

## P1 — Should have (v0.1.x)

- **R9** Shadow-agent / MCP-server inventory for the machine (local scope only).
- **R10** Cursor, Gemini CLI + generic MCP-client support; adapter API for community harnesses.
- **R11** Retention controls (size/time caps) + tamper-evident hash-chaining.

## P2 — Nice to have

- **R13** Fleet aggregation mode (opt-in, self-hosted, multi-user).
- (The former "local replay viewer" is subsumed by the parity Run Timeline/UI.)

## Additions beyond the superseded project (the "extra")

- Open **security-event schema** (`denied`, `policy-fired`, `secret-detected`, `revoked`, `halted`).
- **Coding-agent harness coverage** (Claude Code → Cursor → Codex/Gemini); the shipped project instrumented
  frameworks/raw Python only.
- **Security posture** — redaction-by-default generalized, local-first, hash-chained tamper-evident store,
  fail-closed on tamper.
- **OTel GenAI semconv** + W3C Trace Context.
- MCP server / shadow-agent inventory.

## Explicit non-requirements

- **No injection / intent classification used as a security boundary.** (The rule+LLM anomaly *signals*
  retained from agent-exec-trace are observability signals, not enforcement.)
- **No enforcement actions** (allow / deny / ask / rate-limit) — those are agentpolicy's decisions.
- **No attack-pack / eval framework in this repo** — that is agentdrill.
- No cloud service in v1; not a SIEM.

## Harness compatibility (required)

| Version | Tier-1 coding agents | Tier-2 frameworks |
|---|---|---|
| **v0.1.0** | **Claude Code** | — |
| v0.1.x / v0.2.0 | + Cursor (proxy-interposition where hooks are insufficient) | LangGraph, raw Python (instrumentation SDK) |
| v0.3.0 | + Codex CLI, Gemini CLI; Copilot via OTel/lower layer | + CrewAI, PydanticAI (≥3) |

> **Documented tension:** the ecosystem threshold asks for ≥2 Tier-1 at v0.1.0, while the meta-MVP keeps
> v0.1.0 to Claude Code only. Resolution: v0.1.0 ships Claude Code; Cursor lands in v0.1.x.

## Open questions

- **Runtime (DD-01):** parity with the shipped Python SDK + services may require preserving a compatible
  Python surface rather than a rewrite. See [PRD 10 §E](10-feature-parity.md).
- Cursor full-fidelity recording — native hooks vs proxy interposition for which event classes?
- Schema stewardship: solo steward vs proposing into OTel GenAI from day one (`DD-05`)?
