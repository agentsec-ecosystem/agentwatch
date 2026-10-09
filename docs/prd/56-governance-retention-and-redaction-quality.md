# PRD 56 — Governance, Retention Integrity & Redaction Quality

**BLUF:** Make fleet recording lawful, retention conflict-safe, and redaction honest. A role-based access model for
multi-user/fleet views with self-visible access logs; a privacy notice + DPIA starter generated from the *effective
config*; a legal-hold mechanism that suspends retention and purge; and a published, reproducible **redaction quality**
benchmark so "0 leaks" has a measured recall behind it.

**Status:** shipped in v0.2.0 (2026-10-08) — originally proposed v0.2.0-expanded (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M27–M28 ·
**Depends on:** PRD 44 (IDN-1, CMP-3), PRD 37 (`config explain`), PRD 31 (S21) · **Extends:** IDN-1, CMP-3, `retention apply`,
`purge`, `verify-privacy` · **Adds:** CUJ-31, CUJ-32

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust
> boundary stays deterministic; monitor-only, R2; local-first/no-egress (R6); no new runtime dependency without a decision
> (NFR-5); conformance and quality gates apply (NFR-11).

> Legal features describe product capabilities that **support** legal compliance; they are not legal advice and require
> counsel review before being marketed as meeting a regulation.

Through-line: **who may read whose sessions, what must be kept, and how good redaction really is — all provable.**

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| ACC-1 | Role × data-class access model + self-visible access log | Employee-monitoring review is the EU fleet blocker | 31 |
| ACC-2 | Notice + DPIA starter from effective config | Every adopter rewrites these; unbackable claims must be refused | 31 |
| — | *(ID note: `ACC-*` not `GOV-*` — `GOV-1` is PRD 46's community/governance item.)* | — | — |
| HLD-1 | Legal hold suspends retention/purge, with override provenance | Holds override both retention and erasure; mistaken purge is irreversible | 32 |
| RED-1 | Public redaction corpus + `redact eval` + published numbers | "0 leaks" is only as strong as the pack; PRD 43 pattern | — |

## ACC-1 — Access model & access log · (new)

**Why.** Recording individuals' agent activity triggers monitoring obligations (notice, purpose limits, access control).
IDN-1 hardens hashing and S21 records reads, but fleet/console multi-user views define no roles.

**Behavior.** A documented, enforceable read-access model for fleet/multi-user deployments: roles (self, team reviewer,
security auditor, admin), per-role field visibility (identity hashed vs resolvable; content vs metadata), and mandatory
`store-access` for every cross-user read; users can see who accessed their records.

**Acceptance.**
- [ ] "role × data class" matrix published and tested; cross-role read returns nothing and is itself recorded (FT-ACC-1).
- [ ] A user sees, from their own machine, who (by role) accessed their records and when.
- [ ] Resolving a hashed principal requires an explicit, recorded action by a permitted role.
- [ ] Default fleet profile is least-privileged (metadata-only, hashed identity).

**Dependencies.** PRD 50 (fleet), R13, S21. **Decision.** ADR-0040.

## ACC-2 — Notice & DPIA starter · (new)

**Why.** Rollout requires a notice and an impact assessment that every adopter rewrites.
**Behavior.** `agentwatch governance notice` renders "what is recorded / not / who can see it / how long / how to ask for
erasure" from the live effective config; a DPIA starter in `docs/compliance/`.
**Acceptance.** Every statement maps to a config key or documented guarantee; unbackable statements are omitted and
listed ("refused to claim"); banner "not legal advice".
**Dependencies.** ACC-1, `config explain`, CMP-1 non-certification discipline.

## HLD-1 — Legal hold · (new)

**Why.** Retention windows (AAT §9 12mo) and right-to-erasure (`purge`) collide with litigation holds; today a hold is
only "don't run retention" by convention, invisible to an auditor.
**Behavior.** Place a named hold on a scope (session/project/time/principal). While active, `retention apply` skips held
records and `purge` refuses unless an explicit, recorded override. Holds/releases/overrides are chain records.
**Acceptance.**
- [ ] `hold add/list/release`; `retention apply --dry-run` lists skipped records + hold IDs.
- [ ] Held records survive retention, purge, and index rebuild; `purge` fails closed with the hold ref (FT-HLD-1).
- [ ] Override requires a stated reason and is conspicuous in `evidence` + compliance report.
- [ ] Derived indexes and exports honor holds (EXT-5).
**Dependencies.** CMP-3, EXT-5. **Decision.** ADR-0041.

## RED-1 — Redaction quality benchmark · (new)

**Why.** "0 leaks" rests on the project's own attack pack; buyers and competitors will ask for recall on secret/PII
classes, including structured, encoded and multilingual cases. PRD 43 already publishes detector numbers.
**Behavior.** A versioned, public redaction corpus (synthetic secrets/PII across formats/encodings/languages and
agent-specific shapes) + `agentwatch redact eval --corpus vN` + published per-class recall/false-positive rates.
**Acceptance.**
- [ ] Reproduces published numbers deterministically, offline; CI-guarded against drift.
- [ ] Per class (cloud keys, tokens, private keys, emails, national IDs, free-text PII).
- [ ] Misses listed as known limitations with the proving test; corpus contains no real secrets (governance scan).
**Decision.** D-56.x — corpus licensing + the corpus-version-in-every-number rule.

## Not goals
Legal determinations; HR policy; case management; any claim that agentwatch *certifies* compliance.

## Sources
Claude Code managed/monitoring docs; IDN-1 design; GDPR employee-monitoring practice (counsel review required); PRD 43
pattern; `docs/release/v0.1.0/compliance-matrix.md`. Local analysis files 06, 07, 10.
