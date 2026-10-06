# Design — Streaming Views vs Store Truth

**BLUF:** How the streaming path works without ever moving the integrity boundary: the hook→daemon→store path stays
**append-then-verify**, and every live view is a *derived* read that reconciles to the chain. **How** — the
requirement is [PRD 42](../prd/42-harness-fidelity-and-realtime.md) (STR-1..3).

**Status:** 🚧 M25 **STR-1 implemented** (v0.2.0); live views/tail/soak (STR-2/3) in M26 · **Milestone:** M25–M26 · Sources:
[PRD 42](../prd/42-harness-fidelity-and-realtime.md), PRD 21 (data integrity), PRD 22 (self-observability), S2/S10.

## Invariant

1. Hooks append to the store first; verification happens on the same record path as today. **Streams never bypass
   the chain.**
2. A live stream carries *notification of an appended record* (id + summary), not a competing copy of truth.
3. On any divergence, the **store is authoritative**; the view back-fills from the store.

## Transport

- Daemon → API/UI push over a local socket by default (UDS on Unix, named pipe on Windows — PRD 46 WIN-1); WebSocket
  for the web console.
- Bounded queue per subscriber; on backpressure the subscriber is marked `degraded` and the stream drops to
  summary-only, never blocks the append path (S10 pattern).

## Reconciliation & gaps

- Every subscriber crash/miss triggers a back-fill over the missing seq range.
- A gap that cannot be back-filled is classified with the S2 taxonomy
  (`gap:daemon-down`, `quarantined`, …), surfaced in `coverage` and the live header. **No silent gaps.**
- The live header always states whether recording was continuous over the window (S2/S24 semantics).

## Commands & surfaces

- `agentwatch tail -f` (streaming), live timeline and live anomaly inbox in the operator UI.
- Latency target: p99 hook → operator view ≤ 1 s (perf gate extension).

**STR-2 (M26):** the live consumer is store-truth + notification. The STR-1 transport notifies by sequence number;
[`agentwatch.live.LiveTail`](../../packages/python-sdk/src/agentwatch/live.py) reconciles a poll into rendered
lines, **classified gaps** (`stream-drop`, `purged`, `missing`, `rotated`), and a visible `degraded` flag. A
backpressured subscriber (or a late join, or a rotated store file) is **back-filled from the store**, so the live
view never diverges from the chain. The operator live views themselves are `26.UI-1`.

## Trace correlation

`traceparent` (W3C) propagation through subagents, MCP hops, and SDK spans is applied at append time
([PRD 41](../prd/41-standards-and-interop-ii.md) TRACE); the live tree view consumes the same field. Cross-host
correlation stays within the opt-in self-hosted fleet.

**TRACE-2 (M26):** `agentwatch trace <trace_id>` (and `replay <session> --trace`) reconstruct one causal chain
across every host/session the fleet store holds. Parentage (`parent_span_id`) defines the tree; a child whose
timestamps disagree with its parent across hosts is surfaced as `skew_ms` plus a `clock-skew` gap (never silently
reordered), and a record whose parent span is absent is attached as an orphan with a `missing-parent` gap (never
dropped). Implementation: [`agentwatch.trace`](../../packages/python-sdk/src/agentwatch/trace.py).

## Testing

- Drop-consumer test (no store loss); 24 h streaming soak; a reordered/partial stream never diverges the view from
  the chain; perf gate on the p99 latency.
