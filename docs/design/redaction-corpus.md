# Design — Public Redaction Corpus

**BLUF:** "0 leaks" is only as strong as the attack pack behind it. RED-1 makes the pack **public, versioned, and
reproducible**: a synthetic corpus drives `agentwatch redact eval --corpus vN` to publish per-class recall and a
false-positive rate, offline and deterministically, with known misses declared rather than hidden.

**Status:** implemented (2026-10-07, v0.2.0 M30) · **Milestone:** M30 · Sources:
[PRD 56 §RED-1](../prd/56-governance-retention-and-redaction-quality.md),
[redaction-rules.md](redaction-rules.md), [detector-catalog.md](../reference/detector-catalog.md) (PRD 43 pattern).

## Decision (D-56.x)

- **Corpus licensing:** the corpus is first-party synthetic data, committed under the project license; every value
  is fabricated and **not a real secret**. It is versioned (`schema/vectors/redaction/vN/`) and immutable within a
  version — cases are added under a version bump, never silently edited.
- **Corpus version in every number:** every published metric carries its `corpus` version, so a number is never
  read without knowing which pack produced it.
- **Misses are declared:** a case whose expected class does not fire is a *known miss*, named in
  [known-limitations](../reference/known-limitations.md) with a proving test. Recall is published at its true
  value (e.g. `api-key` 0.8333 because base64-encoded keys are not decoded), never rounded to 1.
- **Governance scan:** because the corpus legitimately contains secret-shaped strings, it is allowlisted for the
  first-party secret scan (`.gitleaks.toml`, `scripts/security/trufflehog-exclude.txt`), like the redaction
  self-test fixtures.

## Implementation

`agentwatch.redact` exposes `load_corpus(version)`, `evaluate_corpus(corpus)`, and `render_report_table(report)`.
`agentwatch redact eval --corpus vN [--json]` prints the published table (human) or the numbers document (JSON).
The machine-readable source of truth is
[`docs/reference/redaction-corpus-numbers.json`](../reference/redaction-corpus-numbers.json), reproduced from the
corpus by `packages/python-sdk/tests/test_redact_eval.py` (drift is a test failure).

## Testing

- `tests/test_redact_eval.py` — determinism offline; committed numbers and generated table cannot drift; per-class
  rates; the false-positive rate; known misses named in known-limitations; corpus registered for the secret scan;
  CLI `redact eval` reproduces the numbers.
