# PRD 09 — Roadmap

**BLUF:** **v0.1.0 ships the entire shipped-feature superset** (all parity + the agentwatch security
additions), porting `agent-exec-trace` first so the old repo can be retained privately at release. Later versions only add
harnesses and integrations — no deferred parity.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## Versions

| Version | Theme | Scope |
|---|---|---|
| **v0.1.0** | **Full PRD scope + shipped-feature superset** | Port the entire `agent-exec-trace` codebase (M0), then: Claude Code recording + OTel GenAI + **security-event schema** + local hash-chained store + replay; instrumentation SDK (LangGraph, raw Python, 4 privacy modes); analytics pipeline + **40 detectors**; FastAPI read API + React operator UI (5 views); Docker stack + demo/seed + E2E; **R9 inventory, R10 harness/framework expansion, R11 retention, R13 fleet aggregation**; NFRs + error handling; compliance evidence. **Parity A1–A6 met; `agent-exec-trace` retained (private).** |
| **v0.1.x** | Harness expansion + polish | Cursor, Codex CLI, Gemini CLI; more Tier-2 framework adapters; fleet aggregation (R13); retention/schema polish |
| **later** | Additions | Bonus AgentWatch ideas (drift/deploy correlation refinements); enterprise integrations |

## Compatibility targets by version

| Version | Tier-1 coding agents | Tier-2 frameworks |
|---|---|---|
| **v0.1.0** | **Claude Code** | LangGraph, raw Python (instrumentation SDK) |
| v0.1.x | + Cursor | + more frameworks |
| later | + Codex CLI, Gemini CLI; Copilot via OTel/lower layer | + CrewAI, PydanticAI (≥3) |

## Parity & migration

- **Parity source:** the shipped `agent-exec-trace` v0.1.0 release (see
  [PRD 10 matrix A](10-feature-parity.md)). **The entire codebase is ported in M0**; `agent-exec-trace` is
  made private at M13 once the ported suite is green in CI (retained, never deleted).
- The instrumentation API (`@trace_agent` / `TracedGraph`) and read-API shapes stay compatible (DD-12).

## Ecosystem dependency

v0.1.0 is the **dependency root** for the Wave 0 meta-MVP: agentpolicy consumes its events, agentdrill
replays its records, agenthalt needs its inventory, and agentcomply turns history into evidence. See the
ecosystem [ROADMAP](https://github.com/agentsec-ecosystem/.github/blob/main/ROADMAP.md).

## Release cadence

Each version ships with: release notes, a compatibility table, and a security audit (org governance floor).
Articles accompany each release per the ecosystem content plan.

## Beyond v0.1.0 — additions (PRD 19–30)

- **v0.1.x:** Cursor (native first, proxy only where needed), Codex CLI, Gemini CLI, more
  frameworks, fleet aggregation — plus the MCP-proxy and OTel-ingestion horizontals (PRD 27) as
  the shape.
- **later:** CrewAI / PydanticAI, Copilot via OTel (i.e., via ingestion), Windows, AgentWatch-#66
  bonus ideas (per-step metrics, trailing baselines, deploy correlation, Slack alerts), the LLM
  assistant (PRD 29) once the local-model story is solid.
- **v0.2.0:** Postgres analytics; the local hash-chained store stays the source of truth.
