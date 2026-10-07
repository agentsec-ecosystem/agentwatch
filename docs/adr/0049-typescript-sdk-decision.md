# ADR-0049 — TypeScript SDK decision (spike; ship deferred to v0.3.0)

- **Status:** accepted (2026-10-06, v0.2.0 M28 TSS-1)
- **Context:** Competitors ship multi-language SDKs and the agent ecosystem is TypeScript-heavy, but a second
  SDK is a major, ongoing commitment (parser parity, conformance, redaction, release engineering). v0.2.0 buys
  the *decision*, not the SDK.
- **Decision:**
  1. **A first-party TypeScript SDK is directionally accepted for v0.3.0, and is not shipped in v0.2.0.** The
     ship/scope decision is re-confirmed at the v0.3.0 planning gate.
  2. The package shape follows the existing Python/JS layout precedent: a `packages/ts-sdk` with a
     provider/processor port of the instrumentation surface (`@trace_agent`, span helpers, privacy modes), not a
     re-architecture.
  3. **The portability premise is proven by a spike, not assumed:** `scripts/generate_ts_types.py` generates
     TypeScript types from the `schema/` JSON Schema, and a round-trip contract test
     (`tests/test_ts_schema_portability.py`) validates a v0.2.0 record against the schema and checks it appears
     in the generated types.
- **Consequences / deferred items:** streaming ingest, OTLP/gRPC, adapter conformance, and the redaction attack
  pack parity are **out of scope** until the v0.3.0 decision; the schema remains the single source of truth so
  generated types stay in lockstep. No new runtime dependency enters the repo in v0.2.0.
- **Alternatives rejected:** a community-only TS SDK (no conformance guarantee); codegen-from-Python instead of
  JSON Schema (the schema is the published contract, PRD 41).
