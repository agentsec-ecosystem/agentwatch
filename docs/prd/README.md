# agentwatch — Product Requirements (v0.1.0)

Requirements for **agentwatch v0.1.0** — the vendor-neutral telemetry and security-event layer for AI
agents. Part of the [agentsec-ecosystem](https://github.com/agentsec-ecosystem).

> **Status: decisions accepted (2026-10-02); ready for the v0.1.0 build.** These PRDs are the v0.1.0 baseline. They supersede the retired
> `agent-exec-trace`/AgentObservatory (#102) and AgentWatch (#66) projects.

## Documents

| # | Document | Covers |
|---|---|---|
| 00 | [Press Release / FAQ](00-press-release.md) | Working-backwards PR/FAQ |
| 01 | [Why](01-why.md) | Problem, evidence, supersession of #102/#66, non-goals |
| 02 | [Architecture](02-architecture.md) | Interception point, components, data flow, standards |
| 03 | [Landscape](03-landscape.md) | Existing tools, whitespace, migration from agent-exec-trace |
| 04 | [Users and CUJs](04-users-and-cujs.md) | Personas + critical user journeys (install/record, replay, export, event) |
| 05 | [What (Features)](05-features.md) | v0.1.0 P0 (R1–R8), parity, non-requirements, compatibility |
| 06 | [Security Baseline](06-security-baseline.md) | Assets, controls, tamper scenarios, disclosure |
| 07 | [Success Metrics](07-success-metrics.md) | Outcome metrics, release gate, anti-metrics |
| 08 | [Risks](08-risks.md) | Risk register, hard parts, triggers |
| 09 | [Roadmap](09-roadmap.md) | Versions, compatibility by version, migration/deprecation |
| 10 | [Feature Parity](10-feature-parity.md) | Every shipped #102/#66 feature → delivered / delegated / waived |
| 11 | [Decisions](11-decisions.md) | Accepted decisions (design, scope, technical, governance) |
| 12 | [Traceability](12-traceability.md) | Requirements → CUJ → WBS → test → parity |
| 13 | [Non-Functional Requirements](13-non-functional-requirements.md) | Perf, storage, privacy, reliability, portability, a11y |
| 14 | [Non-Goals](14-non-goals.md) | Consolidated non-goals |

## Reviewers start here

1. **Scope:** does [PRD 05](05-features.md) define the right v0.1.0 (Claude Code only, monitor-only)?
2. **Journeys:** is [PRD 04](04-users-and-cujs.md) CUJ-1..4 the right first set?
3. **Schema:** is the security-event vocabulary in
   [design/record-format-design.md](../design/record-format-design.md) correct and complete?
4. **Decisions:** review the proposed `DD-01..DD-07` in
   [design/design-decisions.md](../design/design-decisions.md).
5. **Parity:** every feature that **shipped** in the superseded `agent-exec-trace`/AgentObservatory (#102)
   is delivered **in agentwatch** in [PRD 10](10-feature-parity.md) (mandatory, non-delegated). Confirm the
   compatibility approach in §D–§E (instrumentation/read-API compatibility; Python-core runtime).

## Sources

Seeded from the agentsec-ecosystem research base:
`training/research/agent-security/ecosystem/prds/210-agentwatch.md` and
`.../projs/01-agentwatch.md`, plus the interception-points architecture and harness-compatibility matrix.
Absorbed predecessor notes: `projects/Done/102-AgentObservatory.md`, `projects/High/66-AgentWatch.md`.
