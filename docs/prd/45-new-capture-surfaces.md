# PRD 45 — New Capture Surfaces

**BLUF:** Extend the PRD-27 horizontals (native hooks → interposition → ingest → log-read) to the surfaces that
emerged in 2026: **A2A** agent-to-agent delegation with signed agent cards, **LLM-gateway** OTel ingest
(LiteLLM/Portkey), an optional **system-effects** layer (AgentSight/Tracee-shaped), the **Claude Compliance API**,
the long tail of **coding-agent log readers**, and **ACS** (Agent Control Standard) interop — all additive, all
keeping monitor-only, local-first, redaction-before-store, and the deterministic trust path.

**Status:** shipped in v0.2.0 (2026-10-08) — originally proposed v0.2.0 (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M27–M28 ·
**Depends on:** PRD 27, PRD 36, PRD 41, PRD 42 · **Extends:** PRD 27 (Harness Expansion)

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only,
> every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency
> without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **the cheapest fidelity per adapter is interposition and ingest, not bespoke integrations.** Every
surface below is a new `producer` kind or ingest format, not a core-format change — the PRD 27 strategy generalized.

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| A2A-1..2 | Agent-to-agent tasks/delegation recorded across org boundaries | A2A is the agent↔agent standard (150+ orgs); cross-org attribution is where non-repudiation breaks | CUJ-20 |
| GWY-1..2 | Gateway (LiteLLM/Portkey) OTel ingest + exact cost | one recipe turns every gateway deployment into a capture point; exact spend | CUJ-10 |
| SYS-1 | Optional system-effects layer joined to sessions (Linux) | `impact` stops at tool calls; EDR can't see the spawned-process truth | CUJ-8 (extended) |
| CCA-1 | Official Claude Compliance API ingest | authoritative attribution on our home harness; Guardium-class parity | CUJ-14 |
| LOG-1 | Long-tail coding-agent log readers; `log-read` tier | cheapest honest way to shrink the "modeled" gap; ships Windows capture | CUJ-1 (long tail) |
| ACS-1 | ACS Guardian audit-trail ingest | the enforcement ecosystem's decisions become our events | CUJ-8 |

**The "how" lives in design docs:** capture mechanics and formats in
[`design/harness-adapter-design.md`](../design/harness-adapter-design.md) and
[`design/mcp-surface.md`](../design/mcp-surface.md); the foreign-data rule in
[`design/threat-model.md`](../design/threat-model.md).

### A2A-1..2. A2A protocol capture (agent-to-agent horizontal) · v0.2.0 · (new)

**Why.** A2A v1.0 shipped Mar 2026 (multi-protocol bindings, version negotiation, multi-tenancy, **signed agent
cards** for cryptographic identity) and joined the AAIF next to MCP (Aug 2026), backed by 150+ orgs and Google/
Microsoft/AWS. It is the agent↔agent standard; MCP gives us agent↔tools. Cross-org delegation is where NIST says
non-repudiation breaks down, and signed agent cards are free workload identity.

**Behavior.** **A2A-1** `agentwatch a2a-proxy` interposition (mirroring the MCP proxy) recording task lifecycle,
messages, artifacts, and agent-card exchanges, with the same redaction/chain/attribution pipeline.
**A2A-2** record signed agent-card identity provenance + an `agent-delegation` observation; extend `tree`/`trace`
across org boundaries; `ingest --format a2a`.

**Data & schema impact.** New proxy kind + `agent-delegation` event; reuses record construction.

**Security & privacy.** Consent-first + byte-identical restore (D-P); card signature verification outcome is
recorded (verified/unverified), never assumed; artifacts redacted per privacy mode.

**Edge cases.** Long-running tasks (async push + SSE) → bounded; unverifiable card → recorded unverified; version
negotiation → protocol-version fixtures.

**Dependencies.** PRD 27 (N1 proxy), PRD 41 (TRACE/identity), PRD 44 (IDN), PRD 47 (testkit).

**Testing.** Proxy round-trip records both directions; card verification outcome recorded; conformance per A2A spec
version; consent + restore tests.

**Risks & mitigations.** A2A young → version-pin + drift; becoming enforcement → monitor-only preserved.

**Decision.** ADR-0025 — A2A interposition scope + recorded-not-trusted card verification.

### GWY-1..2. Gateway ingest recipes (LiteLLM / Portkey OTel) · v0.2.0 · (cheap) · (new)

**Why.** Enterprises route all model traffic through a gateway (LiteLLM: MIT, self-hosted, air-gapped, per-key/
team/agent/MCP spend tracking, canonical `gen_ai.*` OTel; Portkey: W3C traceparent at the gateway). One recipe turns
each deployment into an agentwatch capture point with zero new adapters, and gateway records carry exact token/cost
metadata.

**Behavior.** **GWY-1** documented + CI-tested ingest recipes (LiteLLM OTel v2, Portkey OTel → `ingest --format
otel`). **GWY-2** exact gateway cost attribution: when records carry exact usage + per-key/team metadata, `cost`
(S6) uses exact numbers, source-stamped.

**Data & schema impact.** Recipes + a cost-source stamp; no record change.

**Security & privacy.** Local file/socket ingest; no egress added.

**Edge cases.** Gateway absent → no effect; mixed exact/estimated cost → per-record source stamp.

**Dependencies.** PRD 41 (OTEL-3), S6, PRD 46 (EXA-1 recipes).

**Testing.** Recipe green in CI against a LiteLLM fixture stream; `cost` shows exact vs estimated.

**Risks & mitigations.** Gateway version churn → pinned fixtures + drift.

**Decision.** D-45.x — which gateway flavors are first-class.

### SYS-1. System-effects ingest layer (Linux, opt-in) · v0.2.0 · (new)

**Why.** `impact` stops at the tool-call layer. AgentSight (SOSP PACMI '25, <3% overhead) proved the
system-effects layer below — syscalls, process lineage, network beyond the model provider — is capturable and
correlates upward; EDR can't answer "did the spawned child process contact anything else?" because a legitimate
process making legitimate calls looks fine.

**Behavior.** Optional ingest of AgentSight/Tracee-shaped system-event streams; join to sessions via process
lineage/time-window; extend `impact`/`blame` blast radius to syscall truth, labeled `source: system-ingest` with
the S11 integrity distinction. **We do not build probes** (Linux-root eBPF violates our portability/trust posture).

**Data & schema impact.** New ingest format + labeled lower layer; no record-schema change.

**Security & privacy.** Linux-only, opt-in, declared-gap elsewhere; lower layer never silently trusted.

**Edge cases.** Lineage false-joins → measured precision (DET-1); macOS/Windows → explicit not-covered.

**Dependencies.** PRD 27 (N2 ingest), S3 impact, B4 quarantine.

**Testing.** A synthetic process tree joins to its session; false-join precision published; `source` label present.

**Risks & mitigations.** Over-trusting a foreign lower layer → explicit labeling + no silent trust.

**Decision.** D-45.y — accepted system-event schemas.

### CCA-1. Claude Compliance API ingest · v0.2.0 · (cheap) · (new)

**Why.** Anthropic ships an official compliance-telemetry API (users, projects, workspaces, admin/config changes,
agent actions, MCP/tool activity); IBM Guardium already consumes it. It is richer than our own hooks on our own home
harness and removes *inferred* attribution where the vendor is authoritative.

**Behavior.** `agentwatch ingest --format claude-compliance` (opt-in, consent-first pull) joined to hook records;
discrepancies surface as classified observations.

**Data & schema impact.** New ingest format feeding IDN-1 identity/principal attribution.

**Security & privacy.** Egress-adjacent → explicit opt-in, pulls recorded as `store-access`, credentials never
stored (session-scoped).

**Edge cases.** Feed vs hook mismatch → classified observation, never silently reconciled; API unavailable → local
records unaffected.

**Dependencies.** PRD 44 (IDN-1), S21 store-access, PRD 27 (N2).

**Testing.** Consent gating; `store-access` recorded; discrepancy classified.

**Risks & mitigations.** Becoming a cloud dependency → opt-in, local-first preserved.

**Decision.** D-45.z — consent + discrepancy policy.

### LOG-1. Coding-agent log readers (long tail) · v0.2.0 · (new)

**Why.** TokenTelemetry proves log-reading scales to 20+ agents (macOS/Linux/Windows) at near-zero engineering per
agent. Reading what agents already write is the cheapest honest way to shrink the "modeled" gap (G5) while native
adapters catch up, and it ships Windows-relevant capture the roadmap defers. Complements COD-1 (Codex) and the
Codex/Claude transcript paths.

**Behavior.** Per-agent readers (Codex, Gemini transcripts where no OTel, Copilot, OpenCode, and the long tail) —
read-only, zero install, local; a new `log-read` fidelity tier in the matrix (between `live-verified` and
`modeled`); `producer: import`.

**Data & schema impact.** `log-read` fidelity label; reuses transcript import (H1).

**Security & privacy.** Read-only (never writes agent files); foreign content through redaction + B4 quarantine;
untrusted-data rule (ADR-0024).

**Edge cases.** Malformed log → quarantined with reason; unknown version → `log-read` range stated, not guessed.

**Dependencies.** PRD 47 (XHT-3 cross-validation), COD-1, ADR-0024.

**Testing.** Fixture per agent/version; cross-parse vs independent OSS parsers; no shell execution.

**Risks & mitigations.** Stale readers → version-tagged fixtures + drift; overclaiming → `log-read` tier honest.

**Decision.** ADR-0024 (shared).

### ACS-1. ACS (Agent Control Standard) interop · v0.2.0 (watch item) · (new)

**Why.** ACM is a new Apache-2.0 wire spec in our niche (GenAI-Security-Project; reference implementation on
Microsoft's Agent Governance Toolkit; Claude Code/OpenCode shims). Guardian decisions (permit/deny/modify) are
precisely our security events with AAT's `record_phase: pre_execution`.

**Behavior.** (a) ingest ACS Guardian audit trails → `denied`/`policy-fired` with pre-execution provenance;
(b) spike emitting ACS-compatible observations for a Guardian to consume. Monitor-only preserved (we never execute a
decision).

**Data & schema impact.** New ingest format; reuses event model.

**Security & privacy.** Enforcement stays in the Guardian; agentwatch records.

**Edge cases.** Spec is young → version-pin + drift (AAT-5 pattern); unknown frame → quarantine.

**Dependencies.** PRD 41 (AAT `record_phase`), PRD 27 (N2).

**Testing.** ACS fixture stream ingests + chains; no decision executes in agentwatch.

**Risks & mitigations.** Premature standard → watch-item priority + re-evaluate at v0.3.0.

**Decision.** D-45.w — ingest-first vs emit-side.

### Documented non-feature: browser-agent capture · v0.2.0 · (decision)

Browser-resident agents (Atlas, Comet, Copilot Mode, Gemini browsing) are out of scope for v0.2.0 — capture would
require a browser extension (new trust surface; CLTC testing notes browser isolation largely holds). Instead:
declare the gap in `known-limitations.md` and verify browser agents' MCP/tool traffic is visible through the
existing host-side proxy where applicable. Revisit if field tests show otherwise.
