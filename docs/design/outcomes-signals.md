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

`agentwatch.digest` groups anomalies/failed calls by a **versioned signature** (`SIGNATURES_VERSION = sg1`) whose
components are, in order: `tool`, `error_class`, `cls1_class` (the most consequential `cls1` category via
`classify.WIDEST_ORDER`), and the session `bd1` behavior fingerprint. Only records that are agent behavior
(`fingerprint.action_tuple` is not `None`) and either failed (`outcome != ok`) or carry a `security_event` are
candidates; internal/marker records never form a pattern.

- `error_class` is a fact: `denied` for a denial, `event:<type>` for an anomaly with no failure outcome, else the
  normalized `tool.response.error`/`message` string (lowercased, whitespace-collapsed, 80-char cap), else `error`.
- Each `FailurePattern` carries `count`, `first_seen`/`last_seen` (UTC), `previous_count` over the **immediately
  preceding window of the same length**, a derived `trend` (`new`/`up`/`down`/`flat`), and up to `TOP_SIGNATURES (5)`
  patterns ranked by count desc, then first-seen asc, then signature key asc.
- `evidence()` yields `replay <session>` per example session and, with ≥2 sessions, `diff <a> <b>` — the pattern links
  to `replay`/`diff`, never to a score.

Grouping rules are versioned; same store → same output (proving test:
`packages/python-sdk/tests/test_outcome_signatures.py`). The `digest` markdown section states the version.

**Deferred:** the console rendering of these patterns is owned by **30.LUI-1** (read-only loopback console, WS-3) and is
not in this branch; the deterministic `digest` side is complete and the console consumes `DigestReport.signatures`
unchanged when it lands.

## Guardrail

No LLM-judged quality; no "score". This stays outside the trust path and inside PRD 29's line (explanation only, never
the boundary). Quality evaluation remains agentdrill.

## Testing

- Deterministic offline; unknown preserved; derivation version shown.
- Rows match hand-computed totals on the field corpus.
- No model/network use (assertion).

## Decision

D-58.x — outcome definitions + derivation versions.
