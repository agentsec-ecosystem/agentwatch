# agentwatch docs

Documentation for **agentwatch** — the vendor-neutral telemetry and security-event layer for AI agents.
Part of the [agentsec-ecosystem](https://github.com/agentsec-ecosystem).

> **Status: v0.1.0 decisions accepted; ready for build.** agentwatch is the **shipped-feature superset** of
> the retired `agent-exec-trace`/AgentObservatory (#102).

## Sections

| Directory | Purpose |
|---|---|
| [prd/](prd/) | Product requirements — why, architecture, landscape, users, features, security, metrics, risks, roadmap, parity, decisions |
| [design/](design/) | Subsystem designs + decisions + threat model, privacy, OTel mapping, data dictionary, a11y |
| [reference/](reference/) | API, SDK, adapter conformance, compatibility, known limitations |
| [wbs/](wbs/) | Work breakdown structure, by version |
| [plans/](plans/) | Execution plans + testing & parity strategy |
| [field-test/](field-test/) | Field test plans and reports, by version |
| [release/](release/) | Release notes, security audits, migration guide, by version |
| [runbooks/](runbooks/) | Operational runbooks |
| [tutorials/](tutorials/) | Hands-on guides |
| [`../schema/`](../schema/) | Machine-readable record + security-event JSON Schema |

Root docs: [glossary](glossary.md) · [distribution](distribution.md) · [gtm](gtm.md) ·
[maintenance backlog](maintenance-backlog.md).

## Quick links

- [PRD index](prd/README.md) · [PRD 10 — Feature Parity](prd/10-feature-parity.md) · [PRD 12 — Traceability](prd/12-traceability.md) · [PRD 13 — NFRs](prd/13-non-functional-requirements.md)
- [Decisions (accepted)](prd/11-decisions.md) · [Design decisions](../docs/design/design-decisions.md)
- [Record format + schema](design/record-format-design.md) · [`schema/`](../schema/)
- [Testing & parity strategy](plans/testing-and-parity-strategy.md)
- [Migration guide (agent-exec-trace → agentwatch)](release/v0.1.0/migration-guide.md)
- [v0.1.0 WBS](wbs/v0.1.0/wbs-v0.1.0-index.md) · [v0.1.0 execution plan](plans/v0.1.0-execution-plan.md)

## Conventions

- **BLUF** — Bottom Line Up Front in major documents.
- **Exit gates** — standardized checklists per milestone.
- **Design decisions** — centralized in `design/design-decisions.md`, referenced as `DD-NN`.
- **Versioned directories** — each documentation type is organized by version.
- **Parity** — every shipped `agent-exec-trace` capability is tracked in [PRD 10](prd/10-feature-parity.md).
