# agentwatch docs

Documentation for **agentwatch** — the vendor-neutral telemetry and security-event layer for AI agents.
Part of the [agentsec-ecosystem](https://github.com/agentsec-ecosystem).

> **Status: v0.1.0 decisions accepted; ready for build.** agentwatch is the **shipped-feature superset** of
> the retired `agent-exec-trace`/AgentObservatory (#102).

## Start here

- [User Guide](USER_GUIDE.md) — install, investigate, compare, triage
- [Architecture tour](architecture-tour.md) — the recording path end to end
- [Development guide](development.md) — layout, setup, quality gates, extending
- [PRD index](prd/README.md) · [Roadmap](../ROADMAP.md)

## Sections

| Directory / file | Purpose |
|---|---|
| [prd/](prd/) | Product requirements — why, architecture, CUJs, features, security, metrics, risks, roadmap, parity, decisions, traceability, NFRs, non-goals |
| [design/](design/) | Subsystem designs + decisions + threat model, privacy, OTel mapping, data dictionary, a11y |
| [reference/](reference/) | API, SDK, adapter conformance, compatibility, limitations, detector catalog, record-format spec, comparison |
| [adr/](adr/) | Architecture Decision Records (ADR-0001..0015) |
| [wbs/](wbs/) | Work breakdown structure, by version |
| [plans/](plans/) | Execution plans + testing & parity strategy |
| [field-test/](field-test/) | Field test plans and reports, by version |
| [release/](release/) | Release notes, security audits, migration guide |
| [runbooks/](runbooks/) | Operational runbooks (install/verify, export, tamper, local stack) |
| [tutorials/](tutorials/) | Hands-on guides (getting started, LangGraph, export, detectors, adapters, replay) |
| [articles/](articles/) | Release-accompanying posts |
| [`../schema/`](../schema/) | Machine-readable record + security-event JSON Schema |

Root docs: [glossary](glossary.md) · [deployment](deployment.md) · [distribution](distribution.md) ·
[gtm](gtm.md) · [maintenance backlog](maintenance-backlog.md).

## Highest-signal links

- [PRD 10 — Feature Parity](prd/10-feature-parity.md) · [PRD 12 — Traceability](prd/12-traceability.md) · [PRD 13 — NFRs](prd/13-non-functional-requirements.md)
- [Decisions (accepted)](prd/11-decisions.md) · [Design decisions](design/design-decisions.md)
- [Record format spec](reference/record-format-spec.md) · [`schema/`](../schema/)
- [Testing & parity strategy](plans/testing-and-parity-strategy.md)
- [Migration guide](release/v0.1.0/migration-guide.md)

## Conventions

- **BLUF** — Bottom Line Up Front in major documents.
- **Exit gates** — standardized checklists per milestone.
- **Design decisions** — centralized in `design/design-decisions.md`; formalized in `adr/`.
- **Versioned directories** — each documentation type is organized by version.
- **Parity** — every shipped `agent-exec-trace` capability is tracked in [PRD 10](prd/10-feature-parity.md).
