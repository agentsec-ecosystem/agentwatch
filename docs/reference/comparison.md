# Reference — Comparison

**BLUF:** How agentwatch differs from adjacent tools. We record agent **behavior + security events**
locally and openly; others do calls, scans, or hosted analytics.

| | agentwatch | LLM observability (LangSmith/LangFuse/Phoenix) | Hosted agent observability (e.g. Explorer) | MCP/agent scanners (agent-scan) |
|---|---|---|---|---|
| Unit recorded | agent behavior + security events | individual LLM calls | traces (hosted) | static config/content |
| Security-event schema | ✅ open, versioned | ✗ | ✗ | ✗ |
| Local-first / no egress | ✅ | varies | ✗ | ✅ |
| Coding-agent coverage | ✅ (Claude Code first) | varies | varies | ✗ |
| Detectors | ✅ 40 | partial | ✅ | ✗ |
| Open license | Apache-2.0 | OSS/varies | proprietary | OSS |
| Enforcement | ✗ (agentpolicy) | ✗ | ✗ | ✗ |

## 2026 landscape update (v0.2.0)

Two clusters compete for adjacent space; neither occupies ours.

**Agent/LLM observability platforms** (LangSmith, Datadog Agent Observability, Langfuse v4-on-ClickHouse, Arize
Phoenix, MLflow, Braintrust, AgentOps): streaming ingestion, OTel-native SDKs, online evals/LLM-judge, automatic
insights/clustering, cost dashboards, long retention tiers. They lack an open security-event schema, tamper
evidence, forensic bundles, and offline verification; most are hosted-first.

**Runtime agent-security platforms** (Polaxis, Prisma AIRS, Tenet, Red Specter, Straiker, Zenity, Why The Agent,
Menlo MARS, Microsoft ISOC): pre-execution enforcement, kill switches, Ed25519-signed trails (Red Specter),
one-click compliance reports (Polaxis), system-level correlation (Tenet). The record is a *side effect of the
product* — proprietary format, no third-party offline verification, mostly closed/hosted.

**The moat (what only agentwatch combines):** open versioned security-event schema + tamper-evident chain with
offline third-party verification + local-first/no-egress default + redaction-by-default (property/fuzz/mutation
proven) + multi-harness capture + replay-as-code + published compatibility honesty + standards mappings + a
published detector-quality bar. Enforcement and attack/eval stay out by design (agentpolicy/agentdrill).

**Risks to the moat (honest):** a big cloud adding an agent-audit module (structurally won't ship open +
offline-verifiable + local-first); Langfuse pivoting to security events; someone shipping a reference AAT
implementation first (why AAT is P0); Langfuse's acquisition uncertainty is a migration moment (a documented
Langfuse→agentwatch OTLP path is cheap insurance).

## 2026-expanded landscape update (PRD 49–59)

Three 2026 clusters moved *around* the record; none occupies it, and two are now data sources rather than rivals.

- **LLM/agent observability platforms** (LangSmith Trajectories/Engine; Langfuse observation-level evals, experiments,
  GitHub-Action regression gates, **CLI + MCP server + SKILL.md**; Phoenix; Datadog/Braintrust/AgentOps): own developer
  attention and the "works with my stack" checklist, but have no open security-event schema, tamper evidence, offline
  verification, or local-first posture. agentwatch answers with a first-minute local console (PRD 54) and
  agent-facing interfaces (PRD 55) — as the *evidence* layer, not a competing dashboard.
- **First-party harnesses** (Claude Code OTel stream + managed settings + auto mode; Cursor Blame; Claude Compliance
  API): now emit authoritative telemetry and enforce permissions. **They are the data source** — agentwatch consumes
  their telemetry (PRD 51), models their authorization truthfully (PRD 49), and deploys through their enterprise
  mechanisms (PRD 50).
- **Code-provenance** (Cursor **Agent Trace** RFC; git-ai Git-notes; Cursor Blame; Jules/Amp/OpenCode/Cline):
  standardized "which lines came from AI, from which conversation". agentwatch is the **evidence-grade source** for
  this ecosystem (PRD 53), not a silo.

**Moat restated:** only agentwatch combines an open versioned security-event schema + tamper-evident chain with
offline verification + local-first/redaction-by-default + multi-harness capture + authorization/oversight provenance +
code provenance + honest fidelity tiers and published effectiveness. Enforcement and attack/eval remain out by design
(agentpolicy/agentdrill).
