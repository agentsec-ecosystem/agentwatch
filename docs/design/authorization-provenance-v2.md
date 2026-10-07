# Design — Authorization Provenance v2

**BLUF:** How the record states **who or what authorized each action** and **what permission mode was in force**, in a
world where the default is a model classifier (auto mode) and bypass is common. Supersedes the S14 five-value
`approval` field with a versioned **authorization source** taxonomy plus a per-call **permission mode**, and defines the
`oversight` report. Observation only — agentwatch records the decision, never makes one.

**Status:** implemented (APV-1/APV-2/APV-3 2026-10-06) · **Milestone:** M29 · Sources:
[PRD 49](../prd/49-authorization-and-oversight.md), [PRD 51](../prd/51-harness-native-telemetry-and-framework-reach.md),
[approval-provenance.md](approval-provenance.md) (legacy), [agent-identity.md](agent-identity.md).

## The problem with the v1 field

`approval ∈ {user, auto, not-required, denied, unknown}` (S14) conflates rule-based auto-approval with the **model
classifier** that is now Claude Code's default, and has no place to say "bypass mode was on, nothing was checking". It
predates auto mode and bypass-as-default behaviour, so it mis-answers the flagship question *"did a human approve that?"*.

## Taxonomy v2 (versioned, additive)

Stored metadata-only. `unknown` remains the honest default when the harness does not expose the fact.

| Field | Values | Meaning |
|---|---|---|
| `authorization.source` | `human-once` · `human-remembered` · `rule` · `classifier` · `hook` · `bypass` · `not-required` · `unknown` | who/what allowed the call |
| `authorization.deny` | `human` · `rule` · `classifier` · `hook` · `unknown` | who/what refused, when `source=denied` |
| `authorization.evidence` | `harness-native` · `inferred` · `session-mode` | how confident the source is |
| `permission_mode` | `default` · `acceptEdits` · `plan` · `auto` · `dontAsk` · `bypassPermissions` · `unknown` | mode in force at the call |

Legacy mapping: `user→human-once`, `auto→rule`, `denied→source=denied`, `not-required→not-required`, `unknown→unknown`.
Historical records keep their stored value; `effective_authorization` maps them at read time. Values are **never written
back silently**.

## Derivation (per harness)

First match wins. Claude Code, with native telemetry (PRD 51, CCO-1) authoritative:

1. native `tool_decision.decision_source` → `config`→`rule`, `hook`→`hook`, `user_permanent`/`user_temporary`→`human-*`,
   `reject`→`denied:human`, classifier→`classifier`.
2. `permission_mode_changed` / session setting → `permission_mode`; a call under `bypassPermissions` → `authorization.source=bypass`
   unless a more specific source is present.
3. hook-only (no native telemetry) → S14 fallback, stamped `authorization.evidence=inferred`; a classifier approval with
   no exposed fact stays `unknown` (never `human`).

Other harnesses (Cursor, Gemini, Codex) map their facts or declare `authorization.source=unknown` per capability.

## `oversight` report

`agentwatch oversight [--since] [--project] [--by day|user|mode|tool-class]`. Facts only:

- authorization mix (calls by source); sessions by starting/ending mode;
- human-prompted calls: approve/reject rate, time-to-decision distribution, sub-second fraction;
- cross-tab: **cls1 destructive/network/credential-adjacent calls × authorization source** (the incident question).

Deterministic, offline, version-stamped. No score. Ratios always carry a denominator; latency shown only when both
prompt and decision timestamps exist, else "n/a (n calls)".

## Privacy

Metadata only; safe under every privacy mode. Identity stays hashed (IDN-1). No content, no values.

## Testing

- Fixture per value proves its derivation; a test proves no value is inferred from `outcome=ok`.
- Classifier approval is never recorded as `user`/`rule` (FT-APV-1).
- Cross-tab matches hand-computed totals (FT-APV-2); bypass interval flagged in `impact`.

## Decision

ADR-0027 — taxonomy v2 + legacy mapping. Legacy table in [approval-provenance.md](approval-provenance.md) is retained
for historical records only.
