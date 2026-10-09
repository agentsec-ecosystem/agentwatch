# ADR-0048 — Plugin API versioning promise

- **Status:** accepted (2026-10-06, v0.2.0 M28 GOV-1)
- **Context:** The agent landscape moves faster than first-party adapters can cover, so a contributor
  ecosystem (community harness adapters and native log readers) is the maturity step. That requires a
  **stable, published contract** contributors can build against — an implicit "it usually works" is not
  enough.
- **Decision:** The adapter plugin contract
  ([adapter API](../reference/adapter-api.md)) is a **public, semver-guaranteed extension surface**:
  `HARNESS_ID`, `CAPABILITIES`, `DOCUMENTED_GAPS`, `normalize`, the adapter error class,
  `conformance.AdapterSpec`, `conformance.register`, and the conformance runner are stable, versioned with
  `agentwatch.protocol.PROTOCOL_VERSION` — **additive within a minor, breaking only in a major with a
  deprecation cycle**. A registered adapter must ship a populated conformance pack (O1) or CI fails. The
  `agent_exec_trace` → `agentwatch` codemod is the supported migration for the legacy import name.
- **Consequences:** The versioning statement lives in the
  [backwards-compatibility policy](../reference/backwards-compatibility-policy.md); the
  [contribution guide](../../CONTRIBUTING.md) documents the "works with X" paths. Community adapters cannot
  drift silently because conformance is enforced in CI.
- **Alternatives rejected:** keeping the contract "experimental" (blocks contribution); a separate plugin
  registry/service (over-engineered for in-repo modules).
