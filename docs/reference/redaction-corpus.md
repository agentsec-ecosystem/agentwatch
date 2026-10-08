# Reference — Public Redaction Corpus (RED-1)

**BLUF:** `agentwatch redact eval --corpus vN` reproduces agentwatch's per-class redaction recall and
false-positive rate from a **versioned, public, synthetic** corpus, fully offline. The committed numbers cannot
drift: a test regenerates them from the corpus and compares. Known misses are honest and listed in
[known-limitations](known-limitations.md).

**Status:** implemented (2026-10-07, v0.2.0 M30) · Sources:
[PRD 56 §RED-1](../prd/56-governance-retention-and-redaction-quality.md), code `agentwatch.redact`.

## Corpus

The corpus lives at [`schema/vectors/redaction/v1/corpus.json`](../../schema/vectors/redaction/v1/corpus.json). Each
case is fabricated; **none is a real secret**. Positive cases assert the expected secret/PII classes fire; negative
cases assert nothing fires (false-positive control). Cases are added, never silently changed, under a version bump.

Run it:

```sh
agentwatch redact eval --corpus v1            # published table
agentwatch redact eval --corpus v1 --json     # machine-readable numbers
```

The machine-readable source of truth is [`redaction-corpus-numbers.json`](redaction-corpus-numbers.json).

## Published numbers (generated)

<!-- BEGIN GENERATED: redaction-corpus-numbers -->
Corpus `v1` — 16 positive / 8 negative case(s).

| Class | Cases | Hits | Recall | Misses |
|---|---|---|---|---|
| api-key | 6 | 5 | 0.8333 | api-key-encoded-base64 |
| oauth-bearer | 1 | 1 | 1.0000 | — |
| jwt | 1 | 1 | 1.0000 | — |
| cloud-secret | 1 | 1 | 1.0000 | — |
| connection-string | 1 | 1 | 1.0000 | — |
| credit-card | 1 | 1 | 1.0000 | — |
| ssn | 1 | 1 | 1.0000 | — |
| email | 2 | 2 | 1.0000 | — |
| phone | 1 | 1 | 1.0000 | — |
| env-secret | 1 | 1 | 1.0000 | — |

Overall recall: **0.9375** (15/16); false-positive rate: **0.0000** (8 negative cases).
<!-- END GENERATED: redaction-corpus-numbers -->

## Honest misses

- `api-key-encoded-base64` — an API key that has been base64-encoded is **not** decoded before detection; the
  `api-key` class therefore publishes 0.8333 recall, not 1.0. This is a declared limitation with a proving test
  (`packages/python-sdk/tests/test_redact_eval.py::test_known_misses_are_listed_as_known_limitations`), not a
  silently rounded-away gap. Encoded/structured secrets remain a known gap.

## Governance scan

The corpus intentionally contains synthetic secret-shaped values, so it is allowlisted for the first-party secret
scan (`.gitleaks.toml` and `scripts/security/trufflehog-exclude.txt`) — the same treatment as the redaction
self-test fixtures. The allowlist is proven by a test
(`packages/python-sdk/tests/test_redact_eval.py::test_corpus_is_registered_for_the_secret_scan`).
