# Reference — Standards Participation Plan

**BLUF:** agentwatch contributes its open security-event vocabulary and authorization taxonomy **into** the
standards other people own, rather than forking them. This is the published plan and owner: the target specs,
what is proposed to each, how contributions are tracked (always "submitted" — **never "adopted"**), and the
quarterly re-pin/engagement cadence that closes [DD-05](../design/design-decisions.md) via
[ADR-0045](../adr/0045-standards-participation.md).

**Status:** published (2026-10-06, v0.2.0-expanded) · **Owner:** the schema steward (agentwatch maintainer) ·
Sources: [PRD 59](../prd/59-owasp-agentic-and-standards-coverage.md) §STD-1,
[PRD 41](../prd/41-standards-and-interop-ii.md), [PRD 39](../prd/39-standards-and-compliance-acceptance.md),
[reference/v0.2.0-research-sources.md](v0.2.0-research-sources.md) §1.

## Owner

The **schema steward** (the agentwatch maintainer who owns `schema/` and the record-format spec) owns this plan:
selecting target specs, authoring and submitting contributions, and keeping the pins current. The role is named
here so the commitment survives any individual: a change of maintainer transfers the owner, not the plan.

## Target specs

| Target spec | Observed pin (2026-10) | What agentwatch proposes | Channel |
|---|---|---|---|
| **OTel GenAI semconv** | `gen_ai.*` registry (semantic-conventions-genai) | the **event vocabulary** and security-event conventions (`gen_ai.*` + our event schema) | upstream issue/PR to the semconv-genai repo |
| **IETF AAT** | `draft-sharif-agent-audit-trail` `-06` (expiry ~Apr 2027) | **authorization taxonomy v2** (`classifier`/`bypass`/`hook`/`rule`/`human-*`) and permission-mode fields | draft comment / mailing-list post |
| **Agent Trace** | `v0.1.0` (RFC, Jan 2026) | the **`capability-changed`** record shape and its provenance linkage | spec issue / RFC comment |
| **OCSF** | `1.5.0` | the security-event class mapping (`agentwatch.*` → OCSF classes, explicit `unmapped`) | OCSF schema issue/PR |
| **OWASP Agentic** | ASI 2026 + Agentic Skills Top 10 (AST10) v1.0 | the coverage vocabulary (`evidence` / `command` / `cannot evidence` / tier) so ASI maps to regenerable evidence | project issue / discussion |

The pins above are re-verified at every re-pin (see **Cadence**); a drift check (`scripts/aat_drift_check.py`,
`scripts/semconv_drift_check.py`) fails CI when an upstream revision moves without our pin being reviewed.

## What is proposed

Three things travel upstream, all derived from work already in this repo (single source of truth — no parallel
implementations):

1. **Event vocabulary.** The versioned security-event schema (`schema/`) and its `agentwatch.*` OCSF mapping —
   proposed as conventions the GenAI semconv group can own, so the open schema becomes a shared default.
2. **Authorization taxonomy v2.** The `classifier`/`bypass`/`hook`/`rule`/`human-*` source taxonomy from
   [PRD 49](../prd/49-authorization-and-oversight.md) (ADR-0027) and its legacy mapping, so a recorded decision
   is portable across harnesses.
3. **`capability-changed`.** The capability/skill drift event (PRD 52) and its provenance linkage, so a change
   in a skill/plugin/hook/rules file is expressible in Agent Trace and OCSF.

## Contributions (submitted)

Every contribution is tracked in the [claims ledger](../release/claims-ledger.json) with status **submitted**.
**"Submitted" is not "adopted":** a submission is an issue, PR, or draft comment we authored; it carries no claim
that a standards body accepted, endorsed, or adopted anything.

| Target spec | Contribution | Status | Ledger |
|---|---|---|---|
| OTel GenAI semconv | security-event vocabulary conventions | submitted, not adopted | `C52` |
| IETF AAT | authorization taxonomy v2 + permission-mode fields | submitted, not adopted | `C53` |
| Agent Trace | `capability-changed` record shape | submitted, not adopted | `C54` |
| OCSF | security-event class mapping (`unmapped` explicit) | submitted, not adopted | `C55` |
| OWASP Agentic | ASI/AST coverage-vocabulary input | submitted, not adopted | `C56` |

## Cadence

Quarterly re-pin and engagement:

| Quarter | Re-pin | Engagement |
|---|---|---|
| Q1 (Jan) | re-verify each spec's latest revision; update the pin table | submit/refresh the quarter's contributions |
| Q2 (Apr) | re-run the drift checks against the new pins | follow up on open submissions |
| Q3 (Jul) | re-verify; record any breaking upstream change as an ADR | submit/refresh |
| Q4 (Oct) | re-verify; annual review of this plan and the owner | submit/refresh |

A quarterly pause is not an excuse to silently drift: if a spec moves and we have not re-pinned, the drift check
fails CI and the owner records why.

## External adopters

The PRD 07 metric is **≥1 non-ecosystem consumer of each export** (OTel, AAT, OCSF/CloudEvents, Agent Trace).
The count is tracked here rather than claimed:

| Export | External adopters (recorded) | Note |
|---|---|---|
| OTel / OCSF / CloudEvents | 0 recorded | counted only when a third party reports consuming our export |
| AAT | 0 recorded | — |
| Agent Trace | 0 recorded | — |

An adopter is counted only when an external party confirms consumption; we do not infer adoption from downloads.

## Non-claims

- We do **not** claim any standard has adopted our proposal. Every contribution is **submitted, not adopted**.
- We do **not** claim conformance or certification from participating; participation is engagement, not endorsement.
- We **do not** fork: improvements go upstream while a repo-local copy is kept until (and if) a spec adopts them
  ([DD-05](../design/design-decisions.md), [ADR-0005](../adr/0005-schema-upstream.md)).
