# PRD 10 — Feature Parity with Superseded Projects

**BLUF:** agentwatch supersedes **agent-exec-trace / AgentObservatory (#102)** and **AgentWatch (#66)**.
This matrix accounts for **every feature of both**, so nothing is silently dropped. Each feature is one of:

- **Delivered** — provided by agentwatch (version noted).
- **Delegated** — provided by a named sibling tool in the ecosystem.
- **Waived** — intentionally not provided, with rationale; **requires sign-off**.

> **Non-regression rule:** before each release, this matrix is reviewed. Any row not yet *Delivered* must
> have a target version or a signed waiver.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## A. Superseded: agent-exec-trace (AgentObservatory, #102)

| Superseded feature | Parity | Delivered by | Version / notes |
|---|---|---|---|
| Behavior trace schema (plan, tool, memory, validation, approval, escalation) | Delivered | agentwatch | Tool calls in v0.1.0; remaining behavior event classes in v0.2.0 |
| Instrumentation wrappers (LangGraph, raw Python) | Delivered | agentwatch | Framework adapters, R10, v0.3.0 |
| OTel/OTLP telemetry pipeline | Delivered | agentwatch | R4, v0.1.0 |
| Loop / cost anomaly **detection** | Delegated | agentpolicy (decisions) + agentdrill (regression packs) | agentwatch exposes records/events; detection is decision logic — v0.3.0 |
| Cost-per-success / tool-overuse **analytics** | Delivered | agentwatch query/analytics | v0.3.0 |
| Run explorer UI (timeline, event detail, drill-down) | Delivered | agentwatch local replay/explorer | R12, v1.x |
| Version comparison | Delivered | agentwatch analytics | v0.3.0 |
| Fleet overview dashboard | **Waived** *(review)* | — | OSS scope ships data + single-session viewer; fleet is commercial territory |
| Policy overlay integration | Delivered | agentwatch + agentpolicy | Security-event schema, R5, v0.1.0 |
| Multi-agent interaction maps | Delivered | agentwatch | v1.x (later) |
| 30-day retention | Delivered | agentwatch | R11, v0.2.0 |
| "Formalize the trace contract before the detector catalog" | Delivered | agentwatch | Sequencing principle (documented in PRD 03/05) |

## B. Superseded: AgentWatch (#66)

| Superseded feature | Parity | Delivered by | Version / notes |
|---|---|---|---|
| Per-step telemetry (step type reason/act/observe/verify, duration, tokens, tool, confidence, error/escalation) | Delivered | agentwatch | Tool calls v0.1.0; step-level + tokens/confidence v0.2.0 |
| Time-series storage, 30-day retention | Delivered | agentwatch | R11, v0.2.0 |
| Fleet overview dashboard | **Waived** *(review)* | — | Same rationale as above |
| Per-agent drill-down | Delivered | agentwatch replay/analytics | v0.3.0 |
| Deployment correlation | Delivered | agentwatch | v0.2.0 |
| Drift detection (trailing baseline, not fixed thresholds) | Delegated | agentpolicy (detection decision) | agentwatch exposes drift **signals** as events; v0.3.0 |
| Slack alert on drift | Delegated | agentinbox (delivery) | v0.3.0 |
| Framework-agnostic SDK (LangGraph callback, raw Python, HTTP API) | Delivered | agentwatch | R10 + adapter API, v0.3.0 |
| ~5ms per-step overhead | Delivered | agentwatch | Performance NFR, v0.2.0 |

## C. Parity decisions requiring sign-off

1. **Drift detection + alerting (AgentWatch)** — proposed **delegated**: agentwatch computes and exposes
   drift **signals**; agentpolicy makes the detection/policy decision; agentinbox delivers the alert.
   This preserves the capability across the ecosystem while keeping agentwatch's "record and expose only"
   boundary. **Confirm this satisfies parity**, or require detection inside agentwatch.
2. **Fleet overview dashboard (both)** — proposed **waived** for OSS. Rationale: the ecosystem deliberately
   ships *data, not dashboards*, per-session local replay covers single-session inspection, and fleet
   discovery/monitoring is commercial territory. **Confirm the waiver**, or require a fleet view (would
   expand v1.x scope).

## D. Preserved design lessons

- **Trace contract first** — schema before any detector/analytics catalog (AgentObservatory lesson).
- **Distinguish "clean run" from "couldn't read the run"** — recording failures are surfaced, never silent
  (see [PRD 06](06-security-baseline.md), fail-closed).
- **Evidence presence vs sufficiency** — annotate records with evidence metadata rather than assuming.
- **Baselines over fixed thresholds** — when drift/analytics land, use trailing baselines (AgentWatch).
- **Instrument a known agent and model the schema from reality** — build order.
