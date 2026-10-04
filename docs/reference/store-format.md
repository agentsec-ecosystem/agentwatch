# Reference — Store Format (v0.1.0)

**BLUF:** The local store is an append-only, hash-chained JSONL file. This is a **published contract**:
the daemon, the CLI, and community adapters write to it; analytics and agentdrill read it.

Status: **experimental** (v0.1.0). Compatibility: additive minor, breaking major + deprecation.
Contract version: `agentwatch.protocol.STORE_FORMAT_VERSION` (currently `1`).

## File

One file per store: `<store.path>/records.jsonl`. Newline-delimited JSON (one object per line), UTF-8.
A crash can leave a partial final line; on the next append the writer starts a fresh line so no valid
record is concatenated onto a fragment.

## Format marker

The first line of a new store is the marker:

```json
{"format": 1}
```

A reader that sees an unknown `format` fails closed (chain not verified) rather than guessing.

## Envelope

Every record line is an envelope. The keys are fixed:

```json
{"seq": 0, "prev_hash": "000…0", "hash": "…", "record": { … }}
```

- `seq` — zero-based, contiguous, monotonically increasing.
- `prev_hash` — the previous entry's `hash`; the genesis entry uses `"0" * 64`.
- `hash` — `sha256(prev_hash + canonical_json(record))`, hex.
- `record` — a schema-valid [`agent-record`](../../schema/agent-record.schema.json).

`canonical_json` is `json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
Any edit to a record (or a deleted line) breaks the chain and is surfaced by verification, never trusted.

## Tombstones (retention + purge)

Retention and single-session purge never hard-delete. A purged entry is rewritten in place as a tombstone
that keeps the chain links but drops the payload:

```json
{"seq": 1, "prev_hash": "…", "hash": "…", "tombstone": true, "purged_at": "2026-…Z"}
```

`seq`/`prev_hash`/`hash` are unchanged, so a tombstoned store still verifies.

## Marker records (metadata-only, agentwatch-authored)

Some actions are recorded as ordinary records with a reserved `tool.name` and
`agent.identity = "agentwatch"`, never as a schema change:

| `tool.name` | Written by | Carries |
|---|---|---|
| `session-purge` | `purge` / retention | session id + optional reason (M9) |
| `operator-note` | `annotate` | redacted note + optional tag, `session_purged` context (M15 S20) |
| `store-access` | `export`, `export-session`, `evidence`, `bom` | command, scope (sessions + record count), destination *kind*, and an `attempted`/`error` pair on failure (M15 S21) |

They are append-only; corrections are new records. The `store-access` allow-list is
exactly "data left, or could leave" — local `search`/`view`/`replay` write nothing.

## Verification

`RecordStore.verify()` recomputes every link and reports the first break as
`ChainStatus(ok=False, broken_at=<seq>)`; `agentwatch verify-store` exits non-zero on a break. A break is
never silent.

## Conformance vectors

[`schema/vectors/`](../../schema/vectors/README.md) publishes valid/tampered/tombstoned/purged/gap/
checkpoint vectors with a machine-readable `expected-verdicts.json`. Two independent implementations —
`RecordStore.verify()` and the standalone [`verify_store.py`](../../schema/vectors/verify_store.py) — run
against the same table in CI (`packages/python-sdk/tests/test_store_vectors.py`); a divergence is a
contract bug. Regenerate with `python scripts/generate_store_vectors.py`.

## Forward compatibility

Frozen stores live under
`packages/python-sdk/tests/fixtures/store-versions/` (one per released format
version, plus the pre-marker legacy shape), declared in `manifest.json`. CI
(`tests/test_forward_compat.py`) asserts every supported store still reads,
verifies, replays, and exports; an unknown `format` fails closed. The set grows
per release.

## Time

Times are stored and compared in UTC and rendered local with an explicit offset;
see the [time rule](time.md).

## Pinned by

`packages/python-sdk/tests/test_protocol_contract.py` (envelope + tombstone shapes), `tests/test_store.py`,
`tests/test_store_vectors.py`, `tests/test_forward_compat.py`.
