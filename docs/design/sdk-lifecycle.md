# Design — SDK Lifecycle, Provider & Sampling

**BLUF:** How the instrumentation SDK is restructured to the OpenTelemetry provider/processor/exporter shape with
flush-on-exit, no-op safety, and a **security-relevant-always-on sampler** that never drops evidence. **How** — the
requirement is [PRD 46](../prd/46-platform-sdk-and-growth.md) (SDK-1..3).

**Status:** ✅ **M25 SDK-1..3 implemented** (v0.2.0) · **Milestone:** M25 · Sources:
[PRD 46](../prd/46-platform-sdk-and-growth.md), PRD 05, PRD 13 (NFRs), OTel trace SDK specification, DD-12.

## Provider

`AgentWatchProvider` owns configuration and produces tracers; configuration changes apply to already-returned
tracers (OTel rule). Processors are registered in order as pipelines:

```
redact → chain → export
```

Exporters: local collector/daemon, OTLP (JSON/gRPC), file, AAT ([aat-mapping.md](aat-mapping.md)).

Batch-processor defaults follow the OTel spec so the SDK feels native: bounded queue (~2048), scheduled export
delay, max batch size, a Simple processor for tests, and ForceFlush on shutdown. Sampling is configurable via our
config layers, with semantic aliases to `OTEL_TRACES_SAMPLER` where the meaning overlaps (kept, not replaced).

## Auto-detect (FWK-2)

`agentwatch.instrument()` is one call that detects the installed supported
frameworks (ADK, Strands, OpenAI Agents SDK via OpenInference, Claude Agent SDK),
points their OTel export at the local collector (standard
`OTEL_EXPORTER_OTLP_ENDPOINT`, plus the OpenInference instrumentor for the OpenAI
Agents SDK), takes identity from the environment, and **prints what it instrumented
and what it could not** — a detected framework that is not wired is reported as a
gap, never dropped silently. It is a **no-op** when the recorder is not running (the
local health endpoint does not answer), registers a single `atexit` ForceFlush, and
is **idempotent** (a second call does not re-wire, so there are no double spans).
Implementation: `agentwatch.autoinstrument`; the public entry point is the callable
`agentwatch.instrument` module (its `invoke_agent`/`set_output` helpers are
unchanged). Framework recipes and tiers: [`framework-recipes.md`](../reference/framework-recipes.md).

## Lifecycle (SDK-1)

- `shutdown()` — at-most-once; idempotent-ish; after shutdown a **valid no-op** tracer is returned; never raises.
- `flush(timeout)` — the OTel `ForceFlush` semantic: exports all pending spans; reports success/failure/timeout;
  bounded.
- Context-manager form (`with AgentWatchProvider(...)`) flushes on exit.
- **Guarantee:** a process that exits normally loses no span; crash tests prove it.

## Concurrency (SDK-3)

Provider, Tracer, and Sampler are documented safe for concurrent use (OTel requirement) with tests; resource
attributes carry `telemetry.sdk.*` / `service.*` for backend recognition.

## Security-relevant-always-on sampler (SDK-2)

- **Never sampled:** security events, `denied`, `secret-detected`, errors, approval decisions.
- **Ratio-sampled:** ordinary successful steps, deterministically — decision = hash(session id, step) (same across
  replays, like OTel `TraceIdRatioBased`).
- **Transparent:** the sampler is visible to `coverage` (S2), which distinguishes "not recorded" from "recorded then
  dropped" (a `sampled-out` marker per window). **No silent gaps.**

This is an agentwatch-native twist on OTel sampling: cost control that cannot discard evidence.

## Compatibility (DD-12)

Existing `@trace_agent` / `TracedGraph` usage is unchanged; the new provider is additive. A migration note documents
the new surface.

## Conformance

An SDK conformance pack registers in the O1 runner like every adapter; the sampler has a property test
(determinism across replays). Implemented in M27 LG-1: `conformance.SdkSpec` replays instrumentation input →
records and passes the same bar (fixture replay, record validation, replay idempotency); the LangGraph pack
(`tests/sdk_conformance_registry.py`) drives the real `_NodeCallbackHandler`, exports spans, and transcodes them.
