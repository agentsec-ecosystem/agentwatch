# Design — Access & Governance

**BLUF:** The read-access model for multi-user/fleet deployments (who may see whose sessions, at what fidelity), the
self-visible access log, and the **notice + DPIA starter generated from the effective config**. Supports lawful
employee-monitoring rollouts; **not legal advice** — counsel review before any compliance claim.

**Status:** proposed (2026-10-05, v0.2.0-expanded) · **Milestone:** M27–M28 · Sources:
[PRD 56](../prd/56-governance-retention-and-redaction-quality.md), [agent-identity.md](agent-identity.md),
[privacy-data-handling.md](privacy-data-handling.md), [derived-postgres.md](derived-postgres.md).

## Role × data-class matrix

| Role | metadata | identity (hashed) | identity (resolved) | content | evidence bundle |
|---|---|---|---|---|---|
| self | ✅ | own | own | per privacy mode | own |
| team reviewer | ✅ | hashed | ✗ | per mode | own team |
| security auditor | ✅ | hashed | recorded resolution | per mode | all |
| admin | ✅ | hashed | recorded resolution | per mode | all |

Enforced and tested. A cross-role read returns **nothing** and is itself recorded (`store-access`, S21). Resolving a
hashed principal to a person requires an explicit, recorded action by a permitted role. Default fleet profile is
least-privileged (metadata-only, hashed identity). ADR-0040.

## Access log

A user can list, from their own machine, who (by role) accessed their records and when — because every cross-user read is a
`store-access` record and the chain is queryable.

## Notice & DPIA starter (ACC-2)

`agentwatch governance notice` renders, from the live effective config (`config explain`): what is recorded, what is not,
who can see it, retention, how to request erasure. **Every statement maps to a config key or documented guarantee**;
unbackable statements are omitted and listed ("refused to claim") so the notice cannot over-promise (e.g., "never leaves
the machine" while an export sink is enabled). A DPIA starter in `docs/compliance/` carries a "not legal advice" banner.

## Identity hashing

Default: on-behalf-of principal and delegation are keyed-hashed (IDN-1); plaintext only under `full`/operator consent.

## Testing

- Matrix enforced; cross-role read empty + logged (FT-ACC-1).
- Notice omits unbackable claims; the omitted list is emitted.
- Identity resolution appears in the subject's access log.
