# Roadmap

**v0.1.0 ships the entire shipped-feature superset** — the whole `agent-exec-trace` codebase is ported first,
then the security layer is added, and the old repo is retained privately at release. **v0.2.0 turns the shipped
record layer into the best-in-class one** (PRD 40–48): standards-native, real harness fidelity, streaming, honest
detector effectiveness, agent identity, and compliance reporting. Later versions add depth and integrations.

| Version | Theme |
|---|---|
| **v0.1.0** | **Full superset** — port all of `agent-exec-trace` → Claude Code recording + OTel GenAI + security-event schema + local store + replay + analytics + 40 detectors + read API + operator UI + stack + demo/E2E; **`agent-exec-trace` retained (private)** |
| **v0.2.0** | **Best-in-class record layer** (PRD 40–48) — IETF AAT emit/ingest; OTel GenAI agent spans + OTLP/gRPC; cross-agent trace correlation; Cursor/Gemini/Codex real fidelity; MCP 2026-07-28 surface; streaming; detector recall program + public eval corpus; agent identity; compliance reports + retention + signing; SIEM/OCSF; A2A/gateway/system-effects/Compliance-API capture; SDK lifecycle; Windows; cross-harness test kit |
| v0.2.x | Postgres analytics (if phased), A2A/system-effects depth, TypeScript SDK decision → ship, more adapters |
| later | CrewAI/PydanticAI full-fidelity; Copilot via OTel; enterprise integrations |

Full detail: [PRD 09 — Roadmap](docs/prd/09-roadmap.md) · [PRD 40 — v0.2.0 Program](docs/prd/40-v0.2.0-program.md) ·
Parity: [PRD 10](docs/prd/10-feature-parity.md) · Porting: [WBS index](docs/wbs/v0.1.0/wbs-v0.1.0-index.md) ·
v0.2.0 WBS: [WBS](docs/wbs/v0.2.0/wbs-v0.2.0-index.md).
