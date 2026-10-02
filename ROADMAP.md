# Roadmap

**v0.1.0 ships the entire shipped-feature superset** — the whole `agent-exec-trace` codebase is ported first,
then the security layer is added, and the old repo is retained privately at release. Later versions only add harnesses
and integrations.

| Version | Theme |
|---|---|
| **v0.1.0** | **Full superset** — port all of `agent-exec-trace` → Claude Code recording + OTel GenAI + security-event schema + local store + replay + analytics + 40 detectors + read API + operator UI + stack + demo/E2E; **`agent-exec-trace` retained (private)** |
| v0.1.x | Cursor / Codex / Gemini; more framework adapters; fleet aggregation |
| later | Additions (AgentWatch ideas, enterprise integrations) |

Full detail: [PRD 09 — Roadmap](docs/prd/09-roadmap.md) · Parity: [PRD 10](docs/prd/10-feature-parity.md) ·
Porting: [WBS index](docs/wbs/v0.1.0/wbs-v0.1.0-index.md).
