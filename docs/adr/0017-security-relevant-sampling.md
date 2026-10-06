# ADR-0017 — Security-relevant sampling

- **Status:** accepted (2026-10-05, v0.2.0) — implemented
- **Context:** see [PRD 46](../prd/46-platform-sdk-and-growth.md) SDK-2 and
  [design/sdk-lifecycle.md](../design/sdk-lifecycle.md). The OTel SDK samples for cost; a security recorder must not
  drop evidence.
- **Decision:** The SDK sampler is **security-relevant-always-on**: security events, `denied`, `secret-detected`,
  errors, and approvals are never sampled; ordinary steps sample deterministically by session-id hash; sampling
  decisions are visible to `coverage` (no silent gaps).
- **Consequences:** Cost control without evidence loss; sampling transparency requires coverage integration; the
  sampler is a trust-path component and gets a property test + mutation coverage.
