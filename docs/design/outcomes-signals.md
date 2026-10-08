# Design — Outcomes & Signals

**BLUF:** How agentwatch produces **deterministic outcome facts** (test/build exits, reverts/resets, interruptions,
retries-to-success, retained-change) and **recurring failure signatures** for `digest`/the console — facts with
denominators and a derivation version, never a quality score. No LLM in the path.

**Status:** proposed (2026-10-05, v0.2.0-expanded) · **Milestone:** v0.2.x · Sources:
[PRD 58](../prd/58-outcomes-ephemeral-capture-and-growth.md), [impact-classification.md](impact-classification.md) (cls1→cls2),
[code-provenance.md](code-provenance.md).

## Outcome facts (OUT-1)

| Fact | Derivation |
|---|---|
| test/build/lint outcome | cls2 exit-status class over command records |
| committed / retained | join to PRV (did changes reach a commit/PR) |
| reverted | session's changed paths later reverted/reset |
| interrupted / rejected | harness interrupt + authorization `denied` |
| retries to success | retry sequences ending in success |

Reported as ratios with numerators/denominators and the derivation version. `cost --per retained-change` joins PRV-1.
Unknown stays unknown. Deterministic: runs with network disabled and no model configured.

Implementation (`agentwatch.outcomes`, `OUTCOME_DERIVATION_VERSION = "out1"`): `build_outcomes` (CLI
`agentwatch outcomes --since 30d --by project|model|harness`) groups by session/project/model/harness and reports
test/build/lint pass **ratios** (`Ratio(numerator, denominator)`; `value` is `None` at 0/0 — unknown stays unknown),
retained / reverted / interrupted / rejected counts, and retries-to-success. Commands are classed by a published,
deterministic table (`OUTCOME_RULES_VERSION = "cls2-out1"`, the cls1 extension); the outcome class is the record
outcome. Retained change (`retained_changes`) joins PRV-1: a session is retained when one of its recorded paths
reaches a later commit (`git log`), and is **unknown** when no repository is supplied — never guessed.
`cost --per retained-change` stamps numerator (total cost), denominator (retained changes), value (or unknown), the
source string, and the derivation version. No LLM and no network anywhere in the path.

## Recurring signatures (OUT-2)

Groups anomalies/failed calls by signature (tool, error class, cls1 class, `bd1` behavior fingerprint) into ranked,
evidence-linked patterns with counts, first/last seen, trend vs prior window, and example sessions (→ `replay`/`diff`).
Grouping rules versioned; same store → same output.

## Guardrail

No LLM-judged quality; no "score". This stays outside the trust path and inside PRD 29's line (explanation only, never
the boundary). Quality evaluation remains agentdrill.

## Testing

- Deterministic offline; unknown preserved; derivation version shown.
- Rows match hand-computed totals on the field corpus.
- No model/network use (assertion).

## Decision

D-58.x — outcome definitions + derivation versions.
