# Design — Environment Fingerprint

**BLUF:** How each session captures a content-free **environment fingerprint** (model, harness version, permission mode,
loaded capability digests, rules-file digest, MCP surface, effective-config digest) so `diff`/`drift` can answer *"what
changed between these sessions?"* — the first question after a regression — without a causal claim.

**Status:** proposed (2026-10-05, v0.2.0-expanded) · **Milestone:** M28 · Sources:
[PRD 57](../prd/57-investigation-depth-and-verification.md), [capability-supply-chain.md](capability-supply-chain.md),
[authorization-provenance-v2.md](authorization-provenance-v2.md), [native-telemetry-join.md](native-telemetry-join.md).

## Contents (names/versions/digests only)

| Component | Source |
|---|---|
| model id/version | native telemetry (CCO) or record metadata |
| harness name/version | adapter + session context |
| permission mode | APV-2 |
| capability digests | CAP-1 (skills/plugins/hooks/rules/memory) |
| rules-file digest | CAP-1 |
| MCP tool surface | S4 snapshot |
| effective-config digest | keyed digest (`config explain`) |

Absent facts are `unknown`; never inferred.

## Diff & drift

- `diff a b` prints the environment delta above the behavior delta.
- `drift --metric M` annotates a detected shift with environment changes in the same window — wording "coincides with",
  never "caused by".
- `sessions --group-by-env` groups by fingerprint, extending `--group-by-behavior`.
- Version Compare (console) can compare by fingerprint, not only agent version label.

## Privacy

Keyed digests; no content. Property-tested: no secrets/values.

## Testing

- A seeded model-version change surfaces first in `diff` (FT-ENV-1).
- Fingerprint stable for an unchanged environment; changes on any component change.
- No causal language in output (assertion).

## Decision

ADR-0042 — fingerprint contents.
