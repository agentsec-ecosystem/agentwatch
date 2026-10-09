# PRD 51 — Harness-Native Telemetry & Framework Reach

**BLUF:** Use the home harness's own telemetry instead of inferring what it already knows, and reach the frameworks
developers actually build on. Ingest Claude Code's OpenTelemetry stream (metrics/events/traces, joined by `tool_use_id`)
for exact tokens/cost/latency and authoritative permission decisions — the same signal Anthropic calls its audit data
source — and add certified OTel-native recipes for ADK, Strands, OpenAI Agents SDK and the Claude Agent SDK so the
embedder journey is one or two lines.

**Status:** shipped in v0.2.0 (2026-10-08) — originally proposed v0.2.0-expanded (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M26–M28 ·
**Depends on:** PRD 41 (OTEL-3), PRD 42 (GEM-1), PRD 44 (IDN), PRD 46 (EXA-1) · **Extends:** A5, S6, PRD 27 N2, GEM-1, CCA-1 · **Adds:** CUJ-21, CUJ-28

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust
> boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only, every hook exits
> 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency without a recorded decision
> (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **the cheapest fidelity is ingest, and the most authoritative source is the harness itself.** Native
telemetry replaces *inference* (cost from transcripts; approval from prompt heuristics) with the vendor's own fields,
while the hook path stays the zero-config default.

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| CCO-1 | Ingest Claude Code OTel; join by `tool_use_id` | Home harness ships metrics/events/traces + SIEM-grade decision facts; plan ingests everything but this | 21 |
| CCO-2 | Claude Agent SDK / headless via the same path | Same CLI/telemetry; many "agents" are Agent-SDK programs | 28 |
| FWK-1 | Certified recipes: ADK, Strands, OpenAI Agents SDK, Claude Agent SDK | Frameworks emit OTel natively; hand-written adapters cannot keep pace | 28 |
| FWK-2 | `agentwatch.instrument()` auto-detect | Competitors onboard in two lines | 28 |

## CCO-1 — Ingest Claude Code's OpenTelemetry stream · (new)

**Why.** Claude Code exports metrics, structured events (`user_prompt`, `api_request`, `tool_result`, **`tool_decision`
with `decision_source`**, `permission_mode_changed`, `mcp_server_connection`) and beta traces, correlated by
`tool_use_id`/`prompt.id`; Anthropic describes the events as the audit data source and a per-user SIEM trail. The plan
ingests Gemini's OTel (GEM-1), Cursor hooks and the Compliance API — not the home harness. Cost today is extracted from
transcripts (A5); native events give exact tokens/cost/latency/cache and the *actual* permission decider (feeds PRD 49).

**Behavior.** agentwatch accepts Claude Code's OTel logs/metrics/traces (local listener or file), maps them into the
record/event model, and **joins by `tool_use_id`** to hook records. Disagreements are classified observations, never
silently reconciled. One consented `init` option (and a managed-settings snippet) enables it.

**Acceptance (what good looks like).**
- [ ] `cost` distinguishes exact (vendor-reported) vs estimated, source-stamped per record (same rule as GWY-2).
- [ ] `approval` uses the native `decision_source` when present (config/hook/user permanent/user temporary/reject/
      classifier), falling back to S14 only with `evidence:"inferred"`.
- [ ] `coverage` reports join rate: "N joined, M hook-only, K otel-only, D discrepancies (classified)".
- [ ] Prompt text / tool details are **not** ingested unless the user enabled them in the harness *and* the privacy mode
      permits; redaction runs on ingest regardless (FT-CCO-1).
- [ ] Offline/local; no egress added; fixtures versioned per Claude Code version with a drift job.

**Data & schema impact.** New `producer/source` values; no record-schema change.
**Security & privacy.** Ingested events pass the privacy pipeline; B4 quarantine for unmappable input.
**Edge cases.** Missing join key → hook-only record; attribute drift → drift job.
**Dependencies.** OTEL-3, IDN-1, privacy pipeline.
**Risks & mitigations.** Vendor attribute churn → pinned fixtures. **Decision.** ADR-0031.

## CCO-2 — Claude Agent SDK / headless runs · (new)

**Why.** The Agent SDK runs the same CLI and emits the same telemetry; one ingest path gives the embedder a zero-code route.
**Behavior.** Documented, tested recipe so an Agent-SDK program's telemetry lands as `source: sdk-native` with identity from resource attributes.
**Acceptance.** Runnable gallery example (EXA-1); conformance fixture; its own compatibility-matrix row with a tier.
**Dependencies.** CCO-1, EXA-1.

## FWK-1 — Certified framework recipes · (new)

**Why.** Google ADK (agent/workflow/model spans), Strands, OpenAI Agents SDK (via OpenInference) and Claude Agent SDK
emit OTel GenAI natively/through community instrumentation; the SDK today is LangGraph + raw Python (+ a PydanticAI shim).
**Behavior.** For ADK, Strands, OpenAI Agents SDK, Claude Agent SDK (plus existing LangGraph/PydanticAI) a documented,
CI-executed recipe routing native/community OTel into agentwatch with correct identity, step mapping and cost; each in
the compatibility matrix with a tier.
**Acceptance.** Each recipe runs in CI against a pinned framework version with a drift job; ingest understands OTel GenAI
and OpenInference-style attributes with explicit `unmapped`; ≤2 lines or 1 config block per framework; mapped records
carry `source` + integrity distinction.
**Dependencies.** OTEL-3, XHT (PRD 47), EXA-1.

## FWK-2 — `agentwatch.instrument()` auto-detect · (new)

**Why.** "Two lines" is the onboarding benchmark.
**Behavior.** One call detects installed supported frameworks, wires their telemetry to the local collector, sets identity
from environment, and reports what it instrumented and what it could not.
**Acceptance.** Prints detected frameworks and gaps (no silent partial instrumentation); no-op safe when agentwatch is
not running (SDK-3); flush-on-exit; idempotent (no double-spans).
**Dependencies.** SDK-1..3, FWK-1. Covers PRD 46 SDK ADRs.

## Not goals

Building an OTel backend (D-Q holds — a transcoder, not storage); requiring OTel for basic recording; shipping the
TypeScript SDK (TSS-1 stays a spike).

## Sources

Claude Code monitoring-usage + Agent-SDK observability docs (2026); Google ADK observability docs; Strands Agents
tracing docs; Arize OpenInference; Datadog/Otel semconv 1.37 note. Local analysis files 02, 04, 07.
