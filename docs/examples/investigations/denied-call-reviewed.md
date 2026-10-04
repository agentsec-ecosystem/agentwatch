# Reviewing a denied call

**The question:** what did the harness refuse, and why?

Seed the store and pull the denial:

```sh run
export DEMO_STORE="${DEMO_STORE:-/tmp/agentwatch-demo}"
python3 scripts/seed-investigations.py --store "$DEMO_STORE"
agentwatch --set store.path="$DEMO_STORE" search --outcome denied
```

You get the `Bash` record with `outcome: denied` and a `denied` security event
carrying the reason (`policy: destructive command refused`). The call never ran —
this is a record of a refusal, not an execution.

Put it in context against a normal session:

```sh run
agentwatch --set store.path="$DEMO_STORE" view sess-denied
agentwatch --set store.path="$DEMO_STORE" diff sess-loop sess-secret
```

`diff` shows how two sessions differ structurally (record counts, failures, and
tools added or removed) — useful when a change in behavior shows up as a new
tool in the mix.

**What to look for:** `denied` outcomes and their reasons; a cluster of denials
in one run is surfaced fleet-wide by the `denied-cluster` detector.

See also: the investigation spec in [`docs/prd/26-investigation.md`](../../prd/26-investigation.md).
