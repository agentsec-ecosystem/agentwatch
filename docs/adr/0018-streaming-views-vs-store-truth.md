# ADR-0018 — Streaming views vs store truth

- **Status:** accepted (2026-10-05, v0.2.0) — implemented
- **Context:** see [PRD 42](../prd/42-harness-fidelity-and-realtime.md) STR-1..3,
  [PRD 41](../prd/41-standards-and-interop-ii.md) TRACE-1..2, and
  [design/streaming-views.md](../design/streaming-views.md). Batch polling (~30 s) is the most visible released
  limitation; streaming adds a lower-latency read path; W3C `traceparent` correlation rides the same boundary.
- **Decision:** The hook→daemon→store path stays **append-then-verify**; streams carry notifications of appended
  records, never a competing copy of truth; views back-fill from the store on divergence; gaps are classified (S2),
  never silent. **Trace propagation** is decided together: `traceparent` is applied at append time only (never
  inferred later), subagents/MCP/SDK spans join one trace id, and cross-host correlation stays within the opt-in
  self-hosted fleet (R13) — no egress.
- **Consequences:** Real-time triage and cross-agent attribution without weakening the integrity boundary; requires
  reconciliation tests and a p99 latency budget (≤1 s).
