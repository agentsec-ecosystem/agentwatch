# Forward-compatibility store fixtures

Frozen stores, one directory per released format version / supported legacy shape
(PRD 38 §Q7, issue #224). `manifest.json` declares each case; `tests/test_forward_compat.py`
asserts every supported store still **reads, verifies, replays, and exports**, and
that an unknown format fails closed.

| Case | Format | Supported | Notes |
|---|---|---|---|
| `v1/` | `1` | yes | current released store format |
| `legacy/` | none (pre-marker) | yes | F4 back-compat: a store with no `{"format": N}` marker |
| `unsupported-v99/` | `99` | no | must fail closed, never guess |

## Growing the matrix

Add a directory per new released format version, generated with the real writer:

```python
from agentwatch.store import RecordStore
store = RecordStore(out / "records.jsonl", durability="none")
store.append(record)
```

Then add the case to `manifest.json`. Entries are removed only at a major. The
`legacy/` case keeps the pre-marker back-compat guarantee (F4) covered; when S26
adds the record `producer` field (M15), this case also asserts an old store reads
with the inferred producer and a format-version note.
