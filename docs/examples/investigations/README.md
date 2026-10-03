# Investigation cookbook

End-to-end, reproducible investigations — not a flag reference. Each narrative
starts from a seeded store, then walks the loop **record → search → replay →
verify → explain** so you can see what an investigation actually looks like.

The dataset is built by [`scripts/seed-investigations.py`](../../../scripts/seed-investigations.py)
and contains no real secrets (the caught secret is already redacted; only the
security event is recorded).

## Seed the demo store

```sh
python3 scripts/seed-investigations.py --store /tmp/agentwatch-demo
export AGENTWATCH_STORE=/tmp/agentwatch-demo   # or pass --set store.path=...
```

The seed creates three sessions:

| Session | Story |
|---|---|
| `sess-loop` | the agent re-reads the same file over and over |
| `sess-secret` | a secret was caught in tool arguments and redacted |
| `sess-denied` | the harness refused a destructive command |

## Narratives

1. [The loop no one noticed](loop-found.md)
2. [The secret that never hit disk](secret-caught.md)
3. [Reviewing a denied call](denied-call-reviewed.md)

See also the spec in [`docs/prd/26-investigation.md`](../../prd/26-investigation.md).
