# agentwatch docs

Documentation for **agentwatch** — the vendor-neutral telemetry and security-event layer for AI agents.
Part of the [agentsec-ecosystem](https://github.com/agentsec-ecosystem).

> **Status: pre-v0.1.0 (Wave 0).** Recording for Claude Code first, monitor-only by default.
> Requirements below are seeded from the ecosystem research base; design content is finalized during v0.1.0 build.

## Sections

| Directory | Purpose |
|---|---|
| [prd/](prd/) | Product requirements — why, architecture, landscape, users, features, security, metrics, risks, roadmap |
| [design/](design/) | Subsystem design documents + centralized design decisions |
| [wbs/](wbs/) | Work breakdown structure, by version |
| [plans/](plans/) | Execution plans, by version |
| [field-test/](field-test/) | Field test plans and reports, by version |
| [release/](release/) | Release notes and security audits, by version |
| [runbooks/](runbooks/) | Operational runbooks |
| [tutorials/](tutorials/) | Hands-on guides |

## Quick links

- [PRD index](prd/README.md)
- [Design decisions](design/design-decisions.md)
- [Record format + security-event schema](design/record-format-design.md)
- [v0.1.0 WBS](wbs/v0.1.0/wbs-v0.1.0-index.md)
- [v0.1.0 execution plan](plans/v0.1.0-execution-plan.md)

## Conventions

- **BLUF** — Bottom Line Up Front in major documents.
- **Exit gates** — standardized checklists per milestone.
- **Design decisions** — centralized in `design/design-decisions.md`, referenced as `DD-NN`.
- **Versioned directories** — each documentation type is organized by version.
- **PRDs live at `docs/prd/`** (not under `design/`).
