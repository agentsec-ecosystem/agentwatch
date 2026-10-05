# PRD 46 — Platform, SDK & Growth

**BLUF:** Make the SDK behave like an industry-standard observability SDK (OTel-shaped provider/lifecycle/
sampler), extend the platform to **Windows**, decide the **TypeScript SDK** direction, publish the read API
contract, ship an executable **examples gallery**, run a structured **v0.2.0 field test**, and grow the
contributor ecosystem — the product motions around the record layer.

**Status:** proposed v0.2.0 (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M25–M28 ·
**M25 subset implemented:** SDK-1/SDK-2/SDK-3 (provider/sampler/lifecycle + conformance pack).
**Depends on:** PRD 05 (SDK), PRD 33, PRD 38 (Engineering Rigor) · **Extends:** PRD 05, PRD 27, PRD 28

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only,
> every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency
> without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **the SDK is the embedder's (P5) surface — it must feel native to anyone who has used an OTel SDK,
and it must not lose records on process exit.** The reference point is the OpenTelemetry SDK specification.

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| SDK-1..3 | OTel-shaped provider/lifecycle + security-relevant sampler; flush-on-exit | v0.1.0 SDK loses records on exit and has no cost control; unblocks PRD 42 LG | CUJ-11 |
| WIN-1 | Windows daemon/service + CI + matrix | enterprise endpoints are Windows; Tier-1 harnesses run there; silent gap today | CUJ-1 (Windows) |
| TSS-1 | TypeScript SDK decision (spike) | competitors ship multi-language SDKs; TS-heavy ecosystem | CUJ-11 (TS) |
| API-1 | OpenAPI publication + typed client | machine-readable contract for ecosystem/SIEM builders | CUJ-4, CUJ-18 |
| EXA-1 | Executable "works with X" recipes | buyers evaluate on "works with what I have" | CUJ-3, CUJ-15 |
| FLD-1 | v0.2.0 field-test program | credibility comes from published field evidence | all |
| GOV-1 | Public plugin API + codemod + contributor guide | contributor ecosystem; landscape moves too fast for first-party adapters | CUJ-1 (community adapters) |

**The "how" lives in design docs:** SDK shape in [`design/sdk-lifecycle.md`](../design/sdk-lifecycle.md);
Windows service/CI posture in [PRD 28](28-performance-operability.md) (service units) plus the v0.1.0 portability
work; API surface in [`reference/api.md`](../reference/api.md).

### SDK-1..3. SDK lifecycle, provider restructure, security-relevant sampler · v0.2.0 · (new)

**Why.** The v0.1.0 SDK (`@trace_agent`, `TracedGraph`, privacy modes) is a thin decorator API: no flush-on-exit
guarantee (records lost on process exit), no sampling/cost control, undefined no-op/concurrency semantics. OTel's
SDK spec has all of these; matching it is what "SDK of this caliber" means and it unblocks PRD 42 (LG-1..2).

**Behavior.** **SDK-1** an `AgentWatchProvider` (config owner) with pluggable processors (redact→chain→export) and
`shutdown()`/`flush(timeout)` at-most-once semantics + valid no-op-after-shutdown + context-manager form.
**SDK-2** a **security-relevant-always-on sampler**: security events/denied/secret/error/approval are never
sampled; ordinary steps are ratio-based and deterministic (hash of session id); sampling decisions are visible to
`coverage` (no silent gaps). **SDK-3** documented + tested concurrency guarantees; `telemetry.sdk.*`/`service.*`
resource attributes; an SDK conformance pack registered in O1.

**Data & schema impact.** Provider/processor/exporter shape; sampling metadata on the summary; no record change.

**Security & privacy.** Security evidence is never dropped; sampling is transparent (coverage) and deterministic.

**Edge cases.** Process exits mid-span → flush; sampler disabled → record all; concurrent tracer creation → safe.

**Dependencies.** PRD 42 (LG-1..2), PRD 41 (PG-3), O1, DD-12 (compat).

**Testing.** Crash/exit tests prove flush; sampler determinism property test; no-op after shutdown; existing
`@trace_agent` users unchanged (DD-12).

**Risks & mitigations.** Quiet record loss → flush-on-exit tests; sampling mistrusted → coverage visibility.

**Decision.** ADR-0017 — sampler semantics + what is never sampled.

### WIN-1. Windows support · v0.2.0 · (new)

**Why.** The roadmap defers Windows to "later," but enterprise endpoints are Windows; every Tier-1 harness runs
there; TokenTelemetry ships Windows capture. The absence is a *silent* gap (not even in known-limitations).

**Behavior.** Named-pipe daemon transport (UDS equivalent), Windows service registration (`init --service`),
a Windows CI leg (hooks + daemon + store + verify + replay), path/encoding hardening, and a Windows column in the
compatibility matrix.

**Data & schema impact.** None (transport + packaging); log-readers (LOG-1) already ship much Windows capture.

**Security & privacy.** Least-privilege file posture adapted to Windows ACLs (PRD 28).

**Edge cases.** Named-pipe permissions differ from UDS; `npx` launcher under PowerShell/cmd verified.

**Dependencies.** PRD 28 (posture/service), PRD 47 (CI), LOG-1.

**Testing.** CUJ-1 passes on Windows ≤15 min; Windows CI leg green.

**Risks & mitigations.** Platform-specific IPC bugs → CI leg + fault-injection extension.

**Decision.** D-46.x — named-pipe security model.

### TSS-1. TypeScript SDK (spike; ship decided at v0.3.0) · v0.2.0 · (new)

**Why.** Competitors ship TS/Go/Java SDKs and the MCP/agent ecosystem is TS-heavy; the embedder persona is
increasingly a TS developer. A full second SDK is a major commitment — v0.2.0 buys the *decision*.

**Behavior.** An ADR + schema-portability spike: package layout, the provider/processor shape ported to TS,
emit-path only (spans → collector/daemon or OTLP), record/redaction shared via the JSON Schema (single source of
truth — generate TS types from `schema/`, never hand-port).

**Data & schema impact.** Consumer-side only; no schema change.

**Security & privacy.** Redaction rules must be data-driven enough to share, or the gap documented honestly.

**Edge cases.** A rule that cannot be shared → documented divergence, not silent.

**Dependencies.** PRD 05, `schema/`, PRD 41 (OTLP).

**Testing.** Round-trip contract test between generated TS types and the schema.

**Risks & mitigations.** Premature second SDK → spike only, ship deferred.

**Decision.** ADR (TSS) — scope + deferred items.

### API-1. OpenAPI publication + typed client · v0.2.0 · (cheap) · (new)

**Why.** Every platform competitor exposes an API contract; ecosystem tools (agentdrill CI replay, agentcomply)
and SIEM builders need the machine-readable contract; it is a precondition for enterprise integration review.
Maintenance-backlog item #1.

**Behavior.** Publish the OpenAPI document for the FastAPI read API; generate a typed Python client in CI,
drift-checked against the live app.

**Data & schema impact.** Docs + generated client.

**Security & privacy.** Read API only; no new exposure.

**Edge cases.** App drifts from the doc → CI fails.

**Dependencies.** Read API (M7), PRD 42 (STR API push).

**Testing.** `openapi.json` present; client contract test fails on drift.

**Decision.** D-46.y — client generation tooling.

### EXA-1. Examples gallery + "works with" recipes · v0.2.0 · (cheap) · (new)

**Why.** Buyers evaluate on "works with what I have"; recipes are proof; the claims ledger keeps them honest.
Competitors market integrations by count; we market *verified* recipes — fewer, executable, honest.

**Behavior.** A curated `examples/` gallery (indexed) with one runnable recipe per story: LiteLLM gateway (GWY),
Phoenix/Jaeger/Tempo export, Splunk/Syslog sink (SIEM), AAT consumer (PRD 41), ACS guardian ingest (ACS-1),
LangGraph instrumentation (LG), fleet aggregation. Each CI-executed (Q10) or compose-covered.

**Data & schema impact.** Docs/examples only.

**Security & privacy.** Recipes carry no secrets (scan).

**Edge cases.** A recipe needing services → compose-covered; illustrative-only → marked with a reason.

**Dependencies.** PRD 38 (Q10 executable docs), PRD 41/42/44/45.

**Testing.** Every recipe green in CI or explicitly illustrative; claims-ledger entries.

**Decision.** D-46.z — recipe coverage list.

### FLD-1. v0.2.0 field-test program · v0.2.0 · (new)

**Why.** v0.1.0's credibility came from published field evidence; the claims ledger requires it; every P0 feature
has an evidence-shaped acceptance criterion needing a program.

**Behavior.** Repeat the v0.1.0 field-test discipline scoped to new surfaces: AAT verified by a real third-party
consumer; Cursor golden-corpus fidelity audit; MCP full-surface conformance; streaming under load; detector
published-numbers reproduction on a second corpus; compliance report reviewed by an auditor-friendly reader.

**Data & schema impact.** `docs/field-test/v0.2.0/` plan + report.

**Security & privacy.** Synthetic/scrubbed data only.

**Edge cases.** A feature with no external verifier → stated as such in the report.

**Dependencies.** All P0 features; PRD 38 (parity checklist).

**Testing.** Every P0 feature appears in ≥1 field case; parity-checklist extended.

**Decision.** D-46.w — field-case roster.

### GOV-1. Community & governance motions · v0.2.0 · (new)

**Why.** OpenSSF Best Practices + Scorecard are in place; the next maturity step is a contributor ecosystem (the
agent landscape moves too fast for first-party adapters — the LOG-1 reader tier is designed for contribution).

**Behavior.** (a) Adapter plugin API documented as a public semver-guaranteed extension surface (the O1 contract);
(b) `agent_exec_trace` → `agentwatch` codemod (maintenance backlog); (c) a "works with X" contribution guide;
(d) ADRs for every v0.2.0 architecture decision (repo convention continued).

**Data & schema impact.** Docs/governance.

**Security & privacy.** Contribution guide includes the redaction/fixture-scan requirements.

**Edge cases.** A community adapter with no conformance registration → CI fails (O1).

**Dependencies.** PRD 27 (O1/J1), PRD 47 (testkit makes contribution cheap).

**Testing.** Codemod tested vs migration-guide examples; plugin versioning statement in the compatibility policy.

**Decision.** D-46.v — plugin API versioning promise.
