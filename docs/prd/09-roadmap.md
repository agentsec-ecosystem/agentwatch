# PRD 09 — Roadmap

**BLUF:** v0.1.0 records Claude Code and publishes the security-event schema; each later version widens
harness coverage and adds inventory/retention without changing the record contract incompatibly.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## Versions

| Version | Theme | Scope |
|---|---|---|
| **v0.1.0** (Wave 0) | Record + schema | Claude Code recording; redaction-by-default; local store; OTel GenAI export; session replay; security-event schema published (R1–R8) |
| **v0.1.x** | Cursor | Cursor adapter (native where possible, proxy interposition where not); retention controls (R11 early) |
| **v0.2.0** | Schema v1 + step telemetry + inventory | Security-event schema v1 hardened; **step-level telemetry** (step type, tokens, confidence) and **behavior event classes** (memory, validation, approval, escalation) from AgentObservatory; **deployment correlation** + **retention/hash-chaining** from AgentWatch; shadow-agent/MCP-server inventory (R9); replay UX |
| **v0.3.0** | Full Tier-1 + frameworks + analytics | Codex CLI, Gemini CLI; Copilot via OTel/lower layer; ≥3 framework adapters (LangGraph, CrewAI, PydanticAI); **analytics/query** (cost-per-success, tool overuse, **version comparison**); **drift signals** exposed (detection/alerting delegated to agentpolicy + agentinbox) |
| **Later** | Scale + viewer | Local replay/explorer viewer (R12); fleet aggregation (R13); multi-agent interaction maps |

## Compatibility targets by version

| Version | Tier-1 coding agents | Tier-2 frameworks |
|---|---|---|
| v0.1.0 | Claude Code | — |
| v0.1.x | + Cursor | — |
| v0.3.0 | + Codex, Gemini, Copilot (lower layer) | ≥3 |

> Ecosystem requirement is ≥2 Tier-1 at v0.1.0; the meta-MVP keeps v0.1.0 to Claude Code and lands Cursor in
> v0.1.x. See [PRD 05](05-features.md).

## Migration & deprecation

- **agent-exec-trace** (#102) — archived, read-only, deprecation notice pointing here. Publish a schema
  mapping from its trace model to the agentwatch record format.
- **AgentWatch** (#66) — absorbed; per-step granularity and baseline ideas survive, alerting moves to
  agentpolicy/agentdrill.
- Both predecessor repos are already transferred and archived under the org with deprecation notices.

## Ecosystem dependency

v0.1.0 is the **dependency root** for the Wave 0 meta-MVP: agentpolicy consumes its events, agentdrill
replays its records, agenthalt needs its inventory, and agentcomply turns history into evidence. See the
ecosystem [ROADMAP](https://github.com/agentsec-ecosystem/.github/blob/main/ROADMAP.md).

## Release cadence

Each version ships with: release notes, a compatibility table, and a security audit (per the org governance
floor). Articles accompany each release per the ecosystem content plan.
