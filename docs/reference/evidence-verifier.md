# Reference — Evidence Verifier (Standalone)

**BLUF:** A bundle only verifiable by installing the tool that produced it is weak evidence. The
standalone `agentwatch-verify` verifier checks an
[evidence bundle](../prd/31-evidence-and-provenance.md) or a
[store/chain file](store-format.md) with **no Python environment, no daemon, and no network** — it
imports nothing from `agentwatch`.

## Build and run

```sh
python scripts/build_verify_zipapp.py --output dist/agentwatch-verify.pyz
python dist/agentwatch-verify.pyz bundle.zip          # exit 0 = intact, 1 = tampered/invalid
python dist/agentwatch-verify.pyz records.jsonl       # verify a store/chain file
python dist/agentwatch-verify.pyz --table schema/vectors/store   # Q6 conformance vectors
```

The zipapp is stdlib-only. The same logic is available in a checkout as
[`scripts/agentwatch_verify/__main__.py`](../../scripts/agentwatch_verify/__main__.py).

## The published reference implementation

An auditor on someone else's laptop may not want to run our build. The ~100-line reference is
[`scripts/agentwatch_verify/reference.py`](../../scripts/agentwatch_verify/reference.py); it is a
second, independent implementation of the same rules and is tested against the same vectors
(`packages/python-sdk/tests/test_verify_zipapp.py`). Drift between the shipped verifier, this
reference, and the [store vectors](../../schema/vectors/README.md) is a test failure.

## What is verified

A bundle on disk is a zip. Verification reads `manifest.json` and checks, independently:

| Verdict | Check |
|---|---|
| **intact** | every member's sha256 matches `manifest.members`, **and** each `records.ndjson` row re-hashes from its `prev_hash` (member tampering and chain edits both fail) |
| **complete** | `coverage.json.complete` (no unexplained gaps) |
| **leak-free** | `privacy.json.leak_free` |

The three are reported separately and never collapsed. An unknown `manifest.bundle_format` is rejected
with the version named; a missing member, a bad zip, or a malformed segment never raises — it returns a
verdict with the problems enumerated.

## Format rules the verifier encodes

- Chain link: `sha256(prev_hash + canonical_json(payload))`, canonical = sorted keys, `(",", ":")`,
  UTF-8, `ensure_ascii=False`. `prev_hash` starts at 64 zeros.
- A checkpoint payload is `{"checkpoint": true, "entries": N, "at": <iso>}`.
- Tombstones keep their links and carry no payload; they verify without re-hashing a record.
