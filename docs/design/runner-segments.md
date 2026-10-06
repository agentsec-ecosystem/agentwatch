# Design — Runner Segments

**BLUF:** How an ephemeral/CI/cloud agent run produces a **self-verifying sealed segment** that imports into a machine's
store with an explicit **chain-of-custody** label. Imported records are kept visibly weaker than locally-chained ones —
same integrity-distinction rule as `union` (S11) — and are never presented as locally witnessed.

**Status:** proposed (2026-10-05, v0.2.0-expanded) · **Milestone:** v0.2.x · Sources:
[PRD 58](../prd/58-outcomes-ephemeral-capture-and-growth.md), [storage-design.md](storage-design.md),
[streaming-views.md](streaming-views.md), PRD 42 (TRACE).

## Segment

A runner-side capture mode writes a sealed segment with:
- its **own hash chain** over the run's records (redacted before store, unchanged pipeline);
- **runner identity** + start/end **attestation** (PRD 50 contents, runner-scoped);
- the records (`source: runner`) and a manifest.

Exported as a CI artifact (the user uploads it; agentwatch performs no egress).

## Import & custody

`agentwatch import-segment seg.zip` verifies the segment chain + attestation and **anchors** it into the local store as a
`source: runner` chain-of-custody record. `verify-store` and `evidence` handle it. The integrity distinction is preserved
and visible in `union`/`sessions`/`provenance`. Tampering fails verification.

## Trace correlation

When `traceparent` is present, TRACE-1 joins a runner session to the originating local session; the cross-host custody
statement travels with the join.

## Privacy

Redacted records only; attack pack passes on segments; zero egress by default.

## Testing

- Tampered segment fails (FT-RUN-1).
- Imported records distinguished from locally witnessed ones.
- No egress (assertion); trace join classifies correctly.

## Decision

ADR-0039 — runner segment custody semantics.
