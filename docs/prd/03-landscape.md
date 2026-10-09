# PRD 03 — Landscape

**BLUF:** Observability for LLM calls is crowded; observability for **agent security** — a vendor-neutral,
local-first, OpenTelemetry record with a *named security-event schema* — is not. The whitespace is the
schema, not the trace viewer.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## What exists today

| Category | Examples | Why it isn't this |
|---|---|---|
| Per-harness telemetry | Claude Code / Cursor consoles | Locked to the harness; not exportable; no security events |
| LLM observability platforms | LangSmith, LangFuse, Phoenix, Helicone | Track individual **LLM calls**, not agent **behavior** or security events; hosted-first |
| Commercial agent observability | Invariant Labs Explorer (→ Snyk) and peers | Hosted, proprietary schema, not local-first |
| MCP/agent scanners | snyk/agent-scan, llm-guard | Scan/analyze static config & content; not a runtime record |
| Kernel tracing | Tetragon, AgentSight, Prempti | Powerful, but Linux-only and not an open event contract; they emit, someone must define semantics |
| Generic OTel | Collector + Tempo/Jaeger/Prometheus/Grafana | The transport, not the agent/security semantics |

## Internal predecessors (superseded)

- **agent-exec-trace** (AgentObservatory, #102) — a shipped behavior-observability stack
  (behavior trace schema, loop/cost anomaly detection, version comparison, run explorer). Retired into
  agentwatch: we keep its OTel-aligned trace schema and its build discipline, and drop the "be the
  analytics + UI product" scope. Precedent: its community feedback demanded *"formalize the trace contract
  before the detector catalog"* — exactly the sequencing agentwatch follows.
- **AgentWatch** (#66) — fleet observability (per-step telemetry, trailing-baseline drift, deployment
  correlation). Retired into agentwatch: per-step granularity and the baseline principle survive;
  detection/alerting moves to agentpolicy/agentdrill.

## Whitespace

1. **The open, versioned security-event schema** — nobody has defined `denied` / `policy-fired` /
   `secret-detected` / `revoked` / `halted` as a portable convention. First to ship it becomes the default.
2. **A "just works" local-first OTel GenAI implementation** with redaction by default.
3. **Unification:** one record that monitoring, enforcement, replay, and compliance all consume.

## Migration from agent-exec-trace

agent-exec-trace was a real, shipped OSS project. The migration path (see [09-roadmap](09-roadmap.md)):

- Publish a mapping from the agent-exec-trace trace schema to the agentwatch record format.
- **Port the entire codebase into agentwatch (WBS M0)**, then **make the old repo private** once its tests are green in CI (WBS M13). It is retained, never deleted.
- Reuse its code (analytics, detectors, UI included) via the port — parity is mandatory and in-repo.

## Honest limitation

Observability alone does not fix bad agents — it gives you the visibility needed to improve and govern
them. agentwatch is deliberately the eyes, not the hands.

## 2026 landscape update (v0.2.0-expanded)

Three clusters moved around the record in 2026; none occupies it.

- **LLM/agent observability platforms** (LangSmith — Trajectories, online evals, Insights/Engine, SmithDB; Langfuse —
  observation-level evals, experiments, GitHub-Action regression gates, **CLI + MCP server + SKILL.md**; Phoenix;
  Datadog, Braintrust, AgentOps): own the developer's attention and the "works with my stack" checklist, but have no open
  security-event schema, tamper evidence, offline verification, or local-first posture.
- **First-party harnesses** (Claude Code OTel stream + managed settings + auto mode; Cursor Blame; Claude Compliance
  API): now emit authoritative telemetry and enforce permissions. **They are the data source** — the record layer should
  consume their telemetry (PRD 51), model their authorization semantics truthfully (PRD 49), and deploy through their
  enterprise mechanisms (PRD 50), not compete with them.
- **Code-provenance** (Cursor **Agent Trace** open spec; git-ai Git-notes; Cursor Blame; Jules/Amp/OpenCode/Cline):
  standardized "which lines came from AI, from which conversation". agentwatch should be the **evidence-grade source**
  for this ecosystem (PRD 53), not a silo.

**The moat, restated:** only agentwatch combines an open versioned security-event schema + tamper-evident chain with
offline third-party verification + local-first/redaction-by-default + multi-harness capture + replay-as-code + agent
identity/authorization provenance + code provenance + honest fidelity tiers and published effectiveness. Enforcement and
attack/eval remain out by design (agentpolicy/agentdrill).

## Doc-visible weaknesses closed by v0.2.0-expanded

These were internal inconsistencies, independent of market trends:

1. **Two products under one name** — CLI/chain store vs the 6-service Compose UI. Closed by the zero-Docker console and
   embedded query tier (PRD 54); PG becomes the fleet/tenant tier.
2. **Hook cost measured at the wrong layer** — in-process p99 published, per-tool-call process cost not. Closed by DEP-3.
3. **Release-gate "partial" rows** (fresh-OS timing R2; second OTel backend R4) — closed by the expanded gate (PRD 07/40).
4. **Recorder survivability unaddressed under managed policy** — closed by PRD 50 (install + attestation).
5. **`approval` predates auto mode** — closed by PRD 49 (taxonomy v2).
6. **Skills/plugins invisible** — closed by PRD 52 despite PRD 01 citing Plugin4Shell.
7. **No non-local agent story** — addressed by PRD 58 (runner segments); Cursor cloud-agent hooks remain a declared gap.

## Sources (2026-expanded)

See `reference/v0.2.0-research-sources.md` §11–§19: Anthropic auto-mode/containment + Claude Code
monitoring/managed-settings/permission-modes docs; CVE-2026-25725; Plugin4Shell; ToxicSkills/ClawHavoc;
Agent Trace RFC + Cognition + git-ai; LangSmith/Langfuse; Google ADK/Strands/OpenInference; Microsoft least-privilege;
OWASP ASI 2026 + Agentic Skills Top 10.
