# Reference — Performance

**BLUF:** The recording path's p99 latency, measured by `scripts/perf_gate.py` and generated from a run — not written by hand.

Generated: 2026-10-03T20:21:15.809088+00:00 · budget: **≤5 ms per step** (NFR-1) · drift tolerance: **3.0×** above a **2.0 ms** floor

| Stage | measured p99 (ms) | NFR cap (ms) | committed baseline p99 (ms) |
|---|---|---|---|
| `daemon_handle_message` | 0.158 | 5.0 | 0.158 |
| `normalize` | 0.011 | 5.0 | 0.011 |
| `redaction` | 0.005 | 5.0 | 0.005 |

> Regenerate with `python scripts/perf_gate.py --update-baseline --write-doc` on the reference runner class. The NFR cap is absolute; the drift tolerance absorbs machine variance. See [performance-budget](../design/performance-budget.md).
