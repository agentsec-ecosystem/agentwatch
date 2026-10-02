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
- Keep the old repo archived and read-only with a deprecation notice pointing here.
- Reuse its documented lessons rather than its analytics/UI surfaces.

## Honest limitation

Observability alone does not fix bad agents — it gives you the visibility needed to improve and govern
them. agentwatch is deliberately the eyes, not the hands.
