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
