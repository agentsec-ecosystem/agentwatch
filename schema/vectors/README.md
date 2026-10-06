# Store / chain conformance vectors

Published test vectors for the [store format](../../docs/reference/store-format.md)
(PRD 38 §Q6, issue #223). A format without vectors is not independently
implementable: these are the "here is a store, here are its hashes, and here is a
tampered one that must fail" cases a third-party verifier, a community adapter, or
an ecosystem consumer can run.

## Layout

| File | Case | Expected verdict |
|---|---|---|
| `store/valid.jsonl` | intact chain | `ok` |
| `store/tampered.jsonl` | a record payload edited, hash not updated | `broken_at=1` |
| `store/tombstoned.jsonl` | retention rewritten old records as tombstones | `ok` |
| `store/purged.jsonl` | `purge_session` tombstoned a session + wrote a marker | `ok` |
| `store/gap.jsonl` | one entry line removed | `broken_at=2` |
| `store/checkpoint.jsonl` | a chain checkpoint appended | `ok` |
| `store/unsupported-format.jsonl` | unknown `format` marker | `broken_at=None, line=1` |
| `store/expected-verdicts.json` | the machine-readable verdict table | — |

`ok` = `(ok, broken_at)` per `agentwatch.store.RecordStore.verify()`. `line` is the
1-based file line for a parse error, `null` otherwise.

## Implementations

Two independent implementations must agree with the table:

1. **`agentwatch.store.RecordStore.verify()`** — the product verifier.
2. **[`verify_store.py`](verify_store.py)** — a standalone, dependency-free
   reference verifier (stdlib only; imports nothing from `agentwatch`). This is
   the reference the M15 **S12** standalone verifier will formalize.

CI runs both against the table (`packages/python-sdk/tests/test_store_vectors.py`);
a verdict that differs between implementations is a contract bug, surfaced.

## Running

```sh
python schema/vectors/verify_store.py --table     # check every vector
python schema/vectors/verify_store.py <store.jsonl>
```

## Regenerating

Vectors are built with the real writer, and the generator asserts the shipped
verifier agrees with the authored verdicts before writing:

```sh
python scripts/generate_store_vectors.py
```

The vector set grows per release; vectors are removed only at a major (PRD 38 §Q7).

---

# AAT conformance vectors

Published test vectors for the [IETF Agent Audit Trail mapping](../../docs/design/aat-mapping.md)
(M26 AAT-4, PRD 41 §AAT-4). A record-interchange format is only trustworthy if a
third party can re-verify it independently: these are the valid, tampered,
unmapped, and unsupported-revision bundles a foreign consumer can replay.

## Layout

| File | Case | Expected verdict |
|---|---|---|
| `aat/valid.json` | intact bundle, all entries chained | `ok` |
| `aat/tampered.json` | entry 1's native record edited, hash not updated | `failed=[1]` |
| `aat/unmapped.json` | records with AAT fields we cannot populate, surfaced in `unmapped` | `ok` |
| `aat/unsupported-revision.json` | unknown `aat_version` | `failed=[-1]` (bundle-level) |
| `aat/expected-verdicts.json` | the machine-readable verdict table | — |

`ok` = no entry failed verification. `failed_entries` lists the 0-based entry
indices that failed the chain hash or inter-entry linkage check; `-1` means the
whole bundle failed (not an object, wrong revision, or no records list).

## Implementations

Two independent implementations must agree with the table:

1. **`agentwatch.aat.verify_aat_report()`** — the product verifier (with
   `verify_aat()` as the boolean convenience form).
2. **[`verify_aat.py`](verify_aat.py)** — a standalone, dependency-free
   reference verifier (stdlib only; imports nothing from `agentwatch`).

CI runs both against the table (`packages/python-sdk/tests/test_aat_vectors.py`);
a verdict that differs between implementations is a contract bug, surfaced.

## Running

```sh
python schema/vectors/verify_aat.py --table      # check every vector
python schema/vectors/verify_aat.py <bundle.json>
```

## Regenerating

Vectors are built with the real `export_aat` writer, and the generator asserts
the shipped verifier agrees with the authored verdicts before writing:

```sh
python scripts/generate_aat_vectors.py
```

