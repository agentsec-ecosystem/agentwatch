# PRD 09 — Roadmap

**BLUF:** v0.1.0 records Claude Code and publishes the security-event schema; each later version restores a
slice of what **shipped** in `agent-exec-trace` until **1.0 reaches full shipped-feature parity** (the
release gate), plus agentwatch's security additions.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## Versions

| Version | Theme | Scope |
|---|---|---|
| **v0.1.0** (Wave 0) | Record + schema | Claude Code recording; redaction-by-default; local store; OTel GenAI export; session replay; security-event schema published (R1–R8) |
| **v0.1.x** | Cursor | Cursor adapter (native where possible, proxy interposition where not); shadow-agent/MCP inventory (R9); retention early (R11) |
| **v0.2.0** | Instrumentation + analytics foundation | **Python SDK parity** (`@trace_agent`, plan/tool/retrieval/memory/approval spans, LangGraph adapter, `AgentTracer` OTLP, 4 privacy modes, version/workload metadata); **analytics pipeline** (trace polling, run summaries, fleet rollup, version cohorts, configurable thresholds); **read API** (`/runs`, `/runs/{id}`, `/fleet`, `/anomalies`); demo + seed/replay; local stack; quality gates |
| **v0.3.0** | Detectors + operator UI | **35 rule-based detectors** (7 categories) + **5 LLM detectors** (feature-flagged); **Run Timeline**, **Fleet Health**, **Anomaly Inbox**; retention + hash-chaining; per-agent drill-down |
| **v1.0** | Full parity | **Version Compare** + **Agent Detail**; all shipped `agent-exec-trace` features delivered **and tested** — the parity release gate; Codex/Gemini CLI, Copilot via lower layer; ≥3 Tier-2 framework adapters |
| **Later** | Additions | opt-in fleet aggregation (R13); bonus AgentWatch ideas if pursued |

## Compatibility targets by version

| Version | Tier-1 coding agents | Tier-2 frameworks |
|---|---|---|
| v0.1.0 | Claude Code | — |
| v0.1.x | + Cursor | — |
| v0.2.0 | + Cursor | LangGraph, raw Python (SDK) |
| v1.0 | + Codex, Gemini, Copilot (lower layer) | + CrewAI, PydanticAI (≥3) |

## Parity & migration

- **Parity source:** the shipped `agent-exec-trace` v0.1.0 release (see
  [PRD 10 matrix A](10-feature-parity.md)). Its instrumentation API (`@trace_agent` / `TracedGraph`) and
  read-API shape must stay compatible, or ship a documented migration.
- **agent-exec-trace** (#102) — archived, read-only, deprecation notice pointing here.
- **AgentWatch** (#66) — never shipped; bonus only.

## Ecosystem dependency

v0.1.0 is the **dependency root** for the Wave 0 meta-MVP: agentpolicy consumes its events, agentdrill
replays its records, agenthalt needs its inventory, and agentcomply turns history into evidence. See the
ecosystem [ROADMAP](https://github.com/agentsec-ecosystem/.github/blob/main/ROADMAP.md).

## Release cadence

Each version ships with: release notes, a compatibility table, and a security audit (org governance floor).
Articles accompany each release per the ecosystem content plan.
