# Reference — Performance

**BLUF:** The recording path's p99 latency, measured by `scripts/perf_gate.py` and generated from a run — not written by hand.

Generated: 2026-10-06T01:22:08.669234+00:00 · recording stages budget **≤5 ms per step** (NFR-1); new M26 paths carry their own per-scenario caps · drift tolerance: **3.0×** above a **2.0 ms** floor

| Stage | measured p99 (ms) | budget (ms) | committed baseline p99 (ms) |
|---|---|---|---|
| `daemon_handle_message` | 0.197 | 5.0 | 0.197 |
| `detector_eval` | 1.876 | 8000.0 | 1.876 |
| `live_tail_poll` | 0.641 | 25.0 | 0.641 |
| `normalize` | 0.020 | 5.0 | 0.020 |
| `otlp_protobuf` | 0.078 | 10.0 | 0.078 |
| `redaction` | 0.005 | 5.0 | 0.005 |

> Regenerate with `python scripts/perf_gate.py --update-baseline --write-doc` on the reference runner class. Recording budgets are absolute (NFR-1); the new-path caps and the drift tolerance absorb machine variance. See [performance-budget](../design/performance-budget.md).
