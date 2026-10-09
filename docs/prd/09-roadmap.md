# PRD 09 — Roadmap

**BLUF:** **v0.1.0 ships the entire shipped-feature superset** (all parity + the agentwatch security
additions), porting `agent-exec-trace` first so the old repo can be retained privately at release. **v0.2.0 turns
the shipped record layer into the best-in-class one** (PRD 40–48): standards-native (AAT, OTel agent spans),
real harness fidelity, streaming, honest detector effectiveness, agent identity, and compliance reporting. Later
versions add depth and integrations — no deferred parity.

**Status:** v0.1.0 shipped · v0.2.0 proposed (2026-10-05) · **Parent:** agentsec-ecosystem #209

## Versions

| Version | Theme | Scope |
|---|---|---|
| **v0.1.0** | **Full PRD scope + shipped-feature superset** | Port the entire `agent-exec-trace` codebase (M0), then: Claude Code recording + OTel GenAI + **security-event schema** + local hash-chained store + replay; instrumentation SDK (LangGraph, raw Python, 4 privacy modes); analytics pipeline + **40 detectors**; FastAPI read API + React operator UI (5 views); Docker stack + demo/seed + E2E; **R9 inventory, R10 harness/framework expansion, R11 retention, R13 fleet aggregation**; NFRs + error handling; compliance evidence. **Parity A1–A6 met; `agent-exec-trace` retained (private).** |
| **v0.2.0** | **Best-in-class record layer** (PRD 40–48) | IETF **AAT** emit/ingest (first reference implementation); **OTel GenAI agent spans** + OTLP/gRPC; **W3C trace correlation** (multi-agent/host); **Cursor/Gemini/Codex** out of "modeled" (native hooks / native OTel / log-readers); **MCP 2026-07-28** full surface + Streamable HTTP; **streaming** daemon + live views; **detector recall program** + public eval corpus + published effectiveness; **agent identity** (AIMS/WIMSE) + delegation; **one-command compliance reports** + retention profiles + signed default; **SIEM/OCSF** sinks; **A2A**, gateway, system-effects, Compliance-API capture; **SDK lifecycle/sampler**; **Windows**; **cross-harness test kit** with honest fidelity tiers. |
| **v0.2.x** | Polish + depth | Postgres analytics tier if phased from v0.2.0 (PG-1..3); A2A/system-effects depth; TypeScript SDK decision → ship; more adapters |
| **later** | Additions | Copilot via OTel; CrewAI/PydanticAI full-fidelity; enterprise integrations; LLM explanation layer hardening |

## Compatibility targets by version

| Version | Tier-1 coding agents | Tier-2 frameworks |
|---|---|---|
| **v0.1.0** | **Claude Code** | LangGraph, raw Python (instrumentation SDK) |
| **v0.2.0** | **Claude Code · Cursor · Gemini CLI · Codex CLI · MCP proxy · OpenCode** | LangGraph, raw Python (full fidelity) |
| later | + Copilot via OTel/lower layer; CrewAI, PydanticAI full-fidelity | + more frameworks |

> Fidelity is declared per harness (`live-verified | fixture-verified | modeled` — PRD 47). v0.2.0's job is to
> remove every "modeled" Tier-1 row honestly, not to imply parity we have not demonstrated.

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

## Beyond v0.1.0 — additions (PRD 19–30, then PRD 40–48)

- **v0.1.x:** Cursor (native first, proxy only where needed), Codex CLI, Gemini CLI, more
  frameworks, fleet aggregation — plus the MCP-proxy and OTel-ingestion horizontals (PRD 27) as
  the shape. *(Superseded in scope by v0.2.0, which lands the full-fidelity versions — see below.)*
- **later:** CrewAI / PydanticAI full-fidelity, Copilot via OTel (i.e., via ingestion),
  AgentWatch-#66 bonus ideas (per-step metrics, trailing baselines, deploy correlation, Slack
  alerts), the LLM assistant (PRD 29) once the local-model story is solid.
- **v0.2.0 (PRD 40–48):** the best-in-class record layer — AAT, OTel agent spans + OTLP/gRPC,
  cross-agent trace correlation, Cursor/Gemini/Codex fidelity, MCP 2026-07-28 surface, streaming,
  detector credibility + public eval corpus, agent identity, compliance reports + retention +
  signing, SIEM/OCSF sinks, A2A/gateway/system-effects/Compliance-API capture, SDK lifecycle,
  Windows, and the cross-harness test kit. **Postgres analytics** lands here or in v0.2.x; the
  local hash-chained store stays the source of truth (PRD 41).
- **v0.2.x / v0.3.0:** TypeScript SDK (decision → ship), A2A/system-effects depth, remaining
  adapters.
