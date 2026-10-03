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
| 13 | [Non-Functional Requirements](13-non-functional-requirements.md) | Perf, storage, privacy, reliability, portability, a11y, **self-observability spec** |
| 14 | [Non-Goals](14-non-goals.md) | Consolidated non-goals |
| 15 | [Data Model & Lifecycle](15-data-model.md) | Entities, identity/versioning, record/session/run lifecycle, invariants |
| 16 | [Configuration Model](16-configuration.md) | Configurables, defaults, locations, validation, fail-closed |
| 17 | [Error Handling & Failure Modes](17-error-handling.md) | Operational failures: detection, fail-closed, recovery |
| 18 | [Security & Compliance Controls](18-security-compliance.md) | OWASP/ATLAS/NIST/ISO/SOC2/OpenSSF mapping + release-gate evidence |
| 19 | [Agent Lifecycle Coverage](19-agent-lifecycle.md) | Session boundaries, denied calls, prompt reason steps, subagent attribution |
| 20 | [Usage & Cost Accounting](20-usage-accounting.md) | Token/model capture; cost computable |
| 21 | [Data Integrity & Delivery Guarantees](21-data-integrity.md) | Spooling, exactly-once, gaps, quarantine, export cursor, format version, checkpoints, repair, least privilege |
| 22 | [Recorder Self-Observability](22-self-observability.md) | `/healthz`, `doctor`, `tail`, continuous chain verification |
| 23 | [Ecosystem Event Interchange](23-event-interchange.md) | Event ingestion, store/socket contract, session export |
| 24 | [Operator Trust & Consent](24-operator-trust.md) | `verify-privacy`, consent-first `init`, harness preflight |
| 25 | [Capture Fidelity & Data Model](25-capture-fidelity.md) | Tool responses, MCP attribution, prompt fingerprint, resumed sessions, project filter |
| 26 | [Query & Investigation Experience](26-investigation.md) | Import, diff, search, terminal view, alerts, purge, cookbook |
| 27 | [Harness Expansion & Conformance](27-harness-expansion.md) | MCP interposition, OTel ingestion, conformance runner, version matrix |
| 28 | [Performance & Operability](28-performance-operability.md) | Async hooks, durability, offline proof, service units, soak, file posture, logs |
| 29 | [LLM Explanation Layer](29-llm-explanation.md) | Local-first narrative over redacted records |
| 31 | [Evidence & Provenance](31-evidence-and-provenance.md) | Evidence bundle, standalone verifier, Agent BOM, `producer` field, store-access audit, annotations, redaction receipts |
| 32 | [Coverage & Recorder Trust](32-coverage-and-recorder-trust.md) | Coverage reconciliation, recorder-state audit records, harness-drift canary, quarantine tooling, recorder-attack suite |
| 33 | [Investigation & Impact](33-investigation-and-impact.md) | Change footprint, subagent tree, blame, time window, denied-then-retried, behavior fingerprint, interrupt, digest, cost |
| 34 | [Content-Flow Forensics](34-content-flow-forensics.md) | Untrusted content → argument flow; tracing an exposed secret |
| 35 | [Capture Context](35-capture-context.md) | Approval provenance, context compaction, VCS revision snapshot, OS principal, `demo` |
| 36 | [Standards & Interop](36-standards-and-interop.md) | OCSF/CloudEvents, reference consumer, OTel collector component, event sinks, MCP tool-surface drift |
| 37 | [Configuration, Profiles & Capture Hygiene](37-config-and-capture-hygiene.md) | `config explain`, install profiles, pathological-record guard, SDK/hook union, standalone redactor |
| 38 | [Engineering Rigor](38-engineering-rigor.md) | Property/differential/mutation/fuzz testing, whole-repo CI, perf gate, conformance vectors, compat matrix, error contract, claims ledger, executable docs, WCAG level, time correctness, release pipeline |
| 39 | [Standards & Compliance Acceptance](39-standards-and-compliance-acceptance.md) | EU AI Act mapping, ISO/NIST appendices, open artifact standards, OTel semconv pin, schema stewardship, forensic-soundness, checkpoint notarization/signing, OpenSSF/OSV |

## Reviewers start here

1. **Scope:** does [PRD 05](05-features.md) define the right v0.1.0 (Claude Code only, monitor-only)?
2. **Journeys:** is [PRD 04](04-users-and-cujs.md) CUJ-1..4 the right first set?
3. **Schema:** is the security-event vocabulary in
   [reference/record-format-spec.md](../reference/record-format-spec.md) correct and complete?
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
