# PRD 41 — Standards & Interop II (AAT, OTel Agent Spans, Trace Correlation, Postgres)

**BLUF:** Make agentwatch the neutral, standards-native record layer: emit and ingest the **IETF Agent Audit
Trail** (first reference-grade implementation), conform to the **OTel GenAI agent-span** vocabulary over
**OTLP/gRPC**, correlate records across agents/hosts/services with **W3C Trace Context**, and give the local
hash-chained store a **derived Postgres analytics tier** with multi-tenant isolation and SDK/hook unification.

**Status:** proposed v0.2.0 (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M25–M27 ·
**Depends on:** PRD 23, PRD 27, PRD 36, PRD 39

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only,
> every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency
> without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **a moving standard under a stability claim is a liability; conforming to it is a moat.** Each
section pairs the standard with the pinning policy that keeps our claim honest.

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| AAT-1..5 | Records emitted/ingested in the IETF AAT shape, conformance-vector-verified | EU AI Act Art. 12(2) requires "recognized standards"; nobody has shipped a reference AAT impl | CUJ-15 |
| OTEL-1..4 | Canonical OTel GenAI **agent-span** conformance + OTLP/gRPC ingest | semconv moved repos; we pin 1.29.0 while backends ingest 1.37+; JSON-only blocks enterprise pipelines | CUJ-3 (extended) |
| TRACE-1..2 | One causal chain across agents, hosts, and processes | NIST names multi-agent non-repudiation foundational — our `tree` is single-host | CUJ-16 |
| PG-1..3 | Self-hosted query engine at fleet scale; multi-tenant; one store for hooks + SDK | G3 (no multi-tenant quarantine) blocks team adoption; PRD 14 folds SDK unification here | CUJ-11 |

**The "how" lives in design docs:** mapping tables and pinning mechanics in
[`design/aat-mapping.md`](../design/aat-mapping.md) and [`design/otel-mapping.md`](../design/otel-mapping.md);
trace propagation and the derived-index contract in [`design/streaming-views.md`](../design/streaming-views.md) and
[`design/derived-postgres.md`](../design/derived-postgres.md).

### AAT-1..5. IETF Agent Audit Trail — emit, ingest, conform (flagship) · v0.2.0 · (new)

**Why.** `draft-sharif-agent-audit-trail-06` (Sept 2026, Standards Track) defines a JSON record with mandatory
agent-identity/action/outcome/trust fields, hash chaining, **pre-execution recording** ("a denial logged only
after execution provides no evidence it was enforced"), an action taxonomy, and 12-month high-risk retention — i.e.
the record agentwatch already produces. EU AI Act Art. 12(2) requires logs conforming to "recognized standards or
common specifications," staged Dec 2027/Aug 2028. First to ship a reference implementation becomes the default hub.

**Behavior.**
- `agentwatch export-session <id> --format aat [--output FILE]` — emit our records in AAT shape.
- `agentwatch ingest --format aat <source>` — validate and chain foreign AAT bundles.
- **AAT-1** record↔AAT field mapping including `record_phase` (pre/post-execution) and identity fields; lossless
  or explicit `unmapped` (never invented). **AAT-2** export. **AAT-3** ingest + quarantine of non-normalizable
  records (B4). **AAT-4** conformance vectors in `schema/vectors/` with a second independent verifier (Q6 pattern).
  **AAT-5** draft-revision pin + drift check (W4 pattern).

**Data & schema impact.** Additive: `record_phase` and identity fields adopted natively where cheap; AAT is an
export/ingest format, not a replacement for the source-of-truth record schema.

**Security & privacy.** Fail-closed validation (F8); foreign content through the secrets pipeline + B4 quarantine;
no egress.

**Edge cases.** A draft revision changes a field → pin + drift job opens an issue; a denial lacking phase evidence
→ `unknown` (never infer); an AAT field we cannot populate → surfaced `unmapped`.

**Dependencies.** PRD 23 (records), PRD 31 (evidence/verifier), PRD 39 (W4/W5 pinning), PRD 44 (IDN-1).

**Testing.** Exported AAT validates against published fixtures; round-trip ingest is lossless-or-explicit; dual
verifiers agree on the vector table; drift job fails on a simulated draft bump.

**Risks & mitigations.** Draft churn → version-pin + explicit unmapped; overclaiming "conformant" → cite the exact
draft revision, never a stable-standard claim.

**Decision.** ADR-0016 — AAT mapping + `lossless-or-explicit` policy + draft pinning.

### OTEL-1..4. Full OTel GenAI agent-span conformance + OTLP/gRPC · v0.2.0 · (new)

**Why.** The GenAI semconv moved to `open-telemetry/semantic-conventions-genai` and now defines agent spans
(`create_agent`, `invoke_agent`, `invoke_workflow`, `plan`, `execute_tool`, skills, command execution). We pin
1.29.0; Datadog ingests 1.37+. And we ingest OTLP JSON only — no gRPC/protobuf (a stated limitation). CUJ-3
("loads into ≥2 common backends unmodified") decays with every semconv release.

**Behavior.** **OTEL-1** re-pin semconv; align span operations to the canonical set; carry the pin in `--version`
and resource attributes with a drift check (extend W4). **OTEL-2** document + property-test the privacy-mode ↔
content-capture mapping (metadata-only by default). **OTEL-3** `agentwatch ingest --format otel` accepts
OTLP/gRPC + protobuf, streaming (no whole-document load). **OTEL-4** skills/command-execution spans where
harnesses expose them; declared gap otherwise.

**Data & schema impact.** Mapping alignment + a new transport; no record-schema change.

**Security & privacy.** Foreign OTLP content redacted before store (B4 quarantine); no egress.

**Edge cases.** Agent-span attributes not present in a source → map what exists, report gaps; 100 MB traces →
streamed.

**Dependencies.** S39 (W4), PRD 27 (N2), PRD 36 (collector component).

**Testing.** Canonical agent-span trees render in ≥2 reference backends (CI); 100 MB ingest within a memory
bound; privacy mode never leaks content on export (redaction suite).

**Risks & mitigations.** Semconv still `Development` → pin + drift + documented policy.

**Decision.** Governed by the W4 pin-and-drift policy (PRD 39), extended to the agent-span vocabulary — the
pinned version, the operation-name alignment, and the move policy are recorded in
[`design/otel-mapping.md`](../design/otel-mapping.md), not a new ADR.

### TRACE-1..2. Distributed trace correlation (W3C Trace Context) · v0.2.0 · (new)

**Why.** NIST AASI names **non-repudiation across multi-agent workflows** foundational — "the attribution chain
for a harmful outcome may span multiple agents that each acted within their own perceived authority." We have
single-host `tree` (S17); the industry needs the multi-host causal chain. G2 in the released limitations.

**Behavior.** **TRACE-1** records carry `traceparent`; subagent fan-out, MCP proxy hops, and SDK spans join one
trace id across processes/hosts (via the opt-in self-hosted fleet, R13). **TRACE-2** `agentwatch trace <tid>`
(and `replay --trace`) reconstructs cross-host causal trees with clock-skew handling (F9 discipline).

**Data & schema impact.** New optional `traceparent` correlation field; derived views.

**Security & privacy.** Correlation stays within the opt-in fleet; no egress.

**Edge cases.** Clock skew across hosts → documented ordering; a propagation break → coverage classifies the gap.

**Dependencies.** A4 (subagent attribution), PRD 46 (SDK spans), fleet (R13), S2 coverage.

**Testing.** A synthetic 3-host/3-harness scenario reconstructs one ordered chain; a broker gap is classified,
not silently absorbed.

**Risks & mitigations.** Cross-host ordering ambiguity → publish the ordering rules; never claim more than the
evidence supports.

**Decision.** ADR-0018 (shared with streaming) — trace-propagation-at-append-time + the correlation contract.

### PG-1..3. Derived Postgres analytics tier, multi-tenant, SDK unification · v0.2.0 (phaseable → v0.2.1) · (new)

**Why.** JSONL does not query at fleet scale (Langfuse→ClickHouse; LangSmith built SmithDB). We have `union` (S11)
but no engine. Multi-tenant isolation is a released limitation (G3). PRD 14 folds SDK→store unification into v0.2.0.

**Behavior.** **PG-1** a **derived, rebuildable** Postgres index — the hash-chained store stays the source of
truth; `--rebuild` reproduces the index (drop-Postgres mode works, slower). **PG-2** multi-tenant isolation for the
self-hosted console + API. **PG-3** SDK spans land in the unified store (chain-protected) with the read-time
`union` as the no-Postgres fallback; the identity/ordering design is recorded (PRD 14's deferred decision).

**Data & schema impact.** New derived store + tenants; no change to the chain format.

**Security & privacy.** Cross-tenant access returns nothing and is `store-access`-recorded; Postgres holds no
content beyond what the chain holds.

**Edge cases.** Postgres unavailable → all commands work from the chain; rebuild after schema drift → validated.

**Dependencies.** PRD 14 decision, S11 `union`, PRD 46 SDK.

**Testing.** Drop-Postgres CI mode green; bit-for-bit rebuild; cross-tenant query returns nothing and is audited.

**Risks & mitigations.** Index drifting from source of truth → architectural invariant (derived-only) + rebuild
test; scope overrun → phase to v0.2.1 first.

**Decision.** ADR-0019 — source-of-truth invariant, rebuild contract, tenancy boundary.
