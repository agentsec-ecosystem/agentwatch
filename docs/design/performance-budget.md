# Design — Performance Budget

**BLUF:** NFR-1 (≤5 ms/step) broken down across the recording path. Each stage has a budget; the sum stays
under the target.

Status: **implemented** (v0.1.0 M12).

## Per-step budget (target ≤5 ms)

| Stage | Budget | Notes |
|---|---|---|
| Hook script → socket send | ≤1 ms | small JSON, UDS |
| Daemon receive + queue | ≤0.5 ms | async |
| Normalize to record | ≤1 ms | pydantic parse |
| Redaction | ≤1.5 ms | regex over arguments |
| Hash-chain append + fsync | ≤1 ms | append-only, single fsync per batch |
| **Total (synchronous to the agent)** | **≤5 ms** | agent is not blocked; the hook returns after send |

> The hook returns after socket send; normalize/store happen asynchronously. The 5 ms target is for the
> synchronous path the agent feels. Throughput (records/s) is bounded by the async pipeline.

## Throughput targets (NFR-7)

- 10k+ traces/day per host (v0.2.0+ ingestion).
- Batch fsync (group commits) to amortize I/O.

## Storage growth (NFR-3)

- Record size: ~0.5–2 KB (metadata-only); bounded by retention (30-day default, 1024 MB cap).
- Estimated: a busy day (~2k tool calls) ≈ 2–4 MB; 30-day retention ≈ 60–120 MB (under the cap).

## Verification

Perf harness `agentwatch.perf.time_call` (M12 12.1). CI tests in `tests/test_perf_budget.py` measure
the in-process step — adapter `normalize` and `Daemon.handle_message` — and fail if p99 > 5 ms (NFR-1).

**Enforced + published (M14 Q4):** `scripts/perf_gate.py` (CI: `.github/workflows/perf.yml`) measures
`normalize`, `redaction`, and `daemon_handle_message` p99, fails above the absolute 5 ms cap or beyond a
3.0× drift band (with a 2.0 ms floor for micro-stage noise), and regenerates the published numbers in
[reference/performance.md](../reference/performance.md) from the run. `--self-test` proves a deliberate
slowdown fails the gate.

## End-to-end hook wall-clock (M29 DEP-3)

The in-process budget above is CPU cost; the latency a developer feels is the **process-spawn cost of a
fresh hook interpreter**, and agentwatch installs two hooks per tool call. `agentwatch.hook_perf` measures
the real `agentwatch-hook pre` wall-clock against a draining socket, and
`scripts/hook_perf_gate.py` (CI: `.github/workflows/hook-perf.yml`) gates it per OS against a committed
baseline (`perf/hook-e2e-baseline.json`), publishing the table in
[reference/performance.md](../reference/performance.md) with a 500-call session overhead quote. The
user-visible budget is **< 500 ms per tool call at p99** (250 ms per hook); a regression beyond the budget
or the 3.0× drift band fails CI and a missed budget yields a tracked ADR, never a silent miss. **Windows is
blocked on WIN-1** (named-pipe transport re-pointed to M31) and is reported blocked, not measured; the
Linux row is pending an `ubuntu-latest` CI run. Decision: [ADR-0030](../adr/0030-hook-wallclock-budget.md).

Durability (`store.durability`, M12 K1) is the operator's explicit fsync choice, surfaced in
`/healthz`: `record` (default, per-record fsync), `checkpoint` (fsync at checkpoints), `none` (no
fsync). The perf test uses `none` to measure CPU, not disk; the durable default is intentionally
stronger than the NFR-1 measurement.
