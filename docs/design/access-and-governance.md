# Design — Access & Governance

**BLUF:** The read-access model for multi-user/fleet deployments (who may see whose sessions, at what fidelity), the
self-visible access log, and the **notice + DPIA starter generated from the effective config**. Supports lawful
employee-monitoring rollouts; **not legal advice** — counsel review before any compliance claim.

**Status:** ACC-1 implemented (2026-10-06, v0.2.0 M29) · **Milestone:** M29 · Sources:
[PRD 56](../prd/56-governance-retention-and-redaction-quality.md), [agent-identity.md](agent-identity.md),
[privacy-data-handling.md](privacy-data-handling.md), [derived-postgres.md](derived-postgres.md).

## Role × data-class matrix (ACC-1)

Implemented in `agentwatch.access`; published by `agentwatch access matrix`.

| Role | metadata | identity (hashed) | identity (resolved) | content | evidence bundle |
|---|---|---|---|---|---|
| self | own only | own only | own only (resolved explicitly) | own, per privacy mode | own |
| team reviewer | ✅ | hashed | ✗ | per mode + own team | own team |
| security auditor | ✅ | hashed | recorded resolution | per mode | all |
| admin | ✅ | hashed | recorded resolution | per mode | all |

Enforced and tested. The `self` role has **no cross-user grant**: a cross-role read returns **nothing** and is itself
recorded (`store-access`, S21). `identity-resolved` is never reachable by a plain read — resolving a hashed principal
to a person requires an explicit, recorded action (`resolve_identity`, permitted roles `security-auditor`/`admin`).
Content is gated on the store actually holding content, so the default fleet profile (metadata-only) cannot leak
arguments. ADR-0040.

## Access log

A user can list, from their own machine, who (by role) accessed their records and when — because every cross-user read is a
`store-access` record and the chain is queryable: `agentwatch access log --owner <id>`.

Role *assignment* (which human holds which role, under a managed policy) is owned by 29.DEP-1 (PRD 50, WS-B); this
module defines and enforces the model and the recording boundary that path must adopt.

## Notice & DPIA starter (ACC-2)

Implemented in `agentwatch.governance`; `agentwatch governance notice` renders, from the live effective config
(`config explain`): what is recorded, what is not, who can see it, retention, how to request erasure. **Every statement
maps to a config key or documented guarantee** (a statement naming an unknown key fails loudly at construction);
unbackable statements are omitted and listed ("refused to claim") so the notice cannot over-promise (e.g., "never leaves
the machine" while an export or event sink is enabled, or any legal-determination claim). A DPIA starter in
[`docs/compliance/dpia-starter.md`](../compliance/dpia-starter.md) carries a "not legal advice" banner and embeds the
`agentwatch governance notice` command.

## Identity hashing

Default: on-behalf-of principal and delegation are keyed-hashed (IDN-1); plaintext only under `full`/operator consent.

## Testing

- Matrix enforced; cross-role read empty + logged (FT-ACC-1) — `tests/test_access.py`.
- Notice omits unbackable claims; the omitted list is emitted (ACC-2) — `tests/test_governance_notice.py`.
- Identity resolution appears in the subject's access log — `tests/test_access.py`.
