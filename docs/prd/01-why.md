# PRD 01 — Why

**BLUF:** Agent systems are opaque in a way normal software is not, and every harness keeps its telemetry
in its own console. The result is a single, shared failure: *"we had no record of what the agent did."*
agentwatch provides that record in a vendor-neutral, OpenTelemetry GenAI format, and defines the
security-event schema the entire ecosystem emits and ingests.

**Status:** v0.1.0 · **Owner:** @deghosal-2026 · **Parent:** agentsec-ecosystem #209

## The problem

1. **No harness ships a complete, exportable, vendor-neutral audit trail of tool calls.** Telemetry stays
   locked in each harness's (or vendor's) console.
2. **OTel GenAI semantic conventions exist but are Development-grade.** There is no "just works"
   implementation — so teams get traces only if they build the pipeline themselves.
3. **No standard security-event semantics exist at all.** There is no agreed way to say "a tool call was
   denied", "a policy fired", "a secret was detected", "a credential was revoked", or "an agent was
   halted" — so nothing downstream can reason about agent security events portably.
4. **Incident forensics and compliance fail on the same line.** The Replit database deletion and the
   Plugin4Shell zero-click RCE postmortems both hit the same wall: no trustworthy record.

## Evidence from the landscape

- Traditional observability (RED metrics: rate, errors, duration) catches infrastructure failures but is
  blind to agent-specific failure modes: **behavioral drift**, **token-cost explosion per task**,
  **confidence collapse**, and **escalation-rate changes**.
- MCP tool poisoning, cross-server shadowing, and rug-pulls are demonstrated and unmitigated at the client
  layer; without a record, none of it is provable after the fact.
- The market consolidated into commercial platforms; the developer-native, local-first, open-record tier is
  empty.

## What this supersedes

agentwatch absorbs two prior projects, both now retired into it:

| Superseded | What it was | What agentwatch takes from it |
|---|---|---|
| **#102 — agent-exec-trace** (AgentObservatory) | Shipped behavior-observability stack: behavior trace schema, instrumentation wrappers, loop/cost anomaly detection, version comparison, run explorer | The OTel-aligned **trace/record schema**, the **"instrument one known agent and model the schema from reality"** build discipline, and hard-won community feedback (distinguish "clean run" from "couldn't read the run"; evidence-presence vs sufficiency; formalize the trace contract before any detector catalog) |
| **#66 — AgentWatch** | Production observability for a 7-agent fleet: per-step telemetry, trailing-baseline drift detection, deployment correlation, framework-agnostic SDK | The **per-step event granularity**, the **trailing-baseline (not fixed-threshold) drift** principle, and **deployment correlation** — reframed as *recording exposes; policy/alerting is a different tool's job* |

Both were valuable but scattered. The ecosystem thesis is **unification**: one install, one record format,
one event schema.

## Why now

Agents now hold shell, filesystem, credential, and tool access on machines that matter. Recording is the
prerequisite for *every* other capability: you cannot alert on, block, or revoke what you never observed.
agentwatch is the first tool installed and is still valuable alone.

## What success looks like

A security team answers *"what did that agent do last Tuesday?"* in under five minutes, from a standard
backend they already own — and other tools (ours and others') emit and consume the same events.

## Non-goals

agentwatch **records and exposes only**. It performs no alerting, no injection/behavioral/intent analysis,
and (in v1) no cloud service and no SIEM. Those belong to agentpolicy, agentdrill, and agentcomply.
