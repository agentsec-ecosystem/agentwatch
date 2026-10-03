# PRD 20 — Usage & Cost Accounting

**BLUF:** Capture token usage and the model version so cost is answerable and behavior is comparable across versions.

**Status:** proposed (2026-10-02) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–29): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification (PRD 14/18); monitor-only, every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

### A5. Capture token usage and model version · M5 (capture) / M6 (rollup) · #169

**Why (evidence).** `tokens`, `cost_usd`, `model_version` are dead fields (PRD 15). Maya (P1)
asks "what did that run cost?" The data is in the transcript every hook event already points to
(`transcript_path`).

**Behavior.** One `session-usage` record per turn (debounced) carries summed tokens and the
model; analytics (M6) computes dollars from a versioned pricing table.

**Data & schema impact.** `tokens` (already in schema), `agent.model_version` (already in
schema). Extractor allow-list: only `message.usage.*` and `message.model` — never content.

**Security & privacy.** The transcript is a raw-prompts file. The extractor is allow-list-only
and proven by a canary test: a transcript seeded with canaries must never yield a record
containing them. This is the single most sensitive new read path and needs explicit review.

**Edge cases.** Missing/locked transcript → one `hook-error`-style note, never a crash.
Multiple models in a session → group by model. `Stop` per turn → debounce to one record/turn;
overwrite semantics live in analytics.

**Dependencies.** A1 (`SessionEnd` for the final flush); M6 pricing table.

**Testing.** Canary test; hand-computed totals fixture; missing-transcript test.

**Risks & mitigations.** Reading raw prompts (canary test + allow-list). Hardcoding prices
(D-19.5: SDK records tokens+model only).

**Decision.** D-19.5 (where cost is computed).

