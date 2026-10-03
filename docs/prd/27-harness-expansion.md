# PRD 27 — Harness Expansion & Conformance

**BLUF:** Grow across harnesses along horizontals — a local MCP-interposition adapter and OTel
GenAI ingestion — instead of N bespoke integrations, all held to one shared conformance bar and a
generated compatibility matrix.

**Status:** proposed (2026-10-02) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–29): fail closed and never silent (PRD 17); redaction before
> storage (DD-06); the trust boundary stays deterministic — no LLM in redaction, validation, or
> chain verification (PRD 14/18); monitor-only, every hook exits 0 (R2); local-first, no egress
> without explicit opt-in (R6); no new runtime dependency without a recorded decision (NFR-5);
> conformance and quality gates apply (NFR-11).

**Strategy.** Depth before breadth: one harness done deeply beats three done shallowly for the
security persona. Then expand at the cheapest fidelity-per-adapter:
**native hooks** (best) → **MCP interposition** (one adapter, many harnesses) → **OTel ingestion**
(shallow, near-zero cost) → **import** (historical). Prioritization is demand-driven from field
tests (M14) and issue traffic, not guessed. PRD 09/11 already sequence a second Tier-1 harness
(Cursor) into v0.1.x and reserve proxy interposition for it (B1/DD-15); this PRD generalizes it.

### N1. MCP-client interposition adapter (one adapter, N harnesses) · M10 · #212

**Why (evidence).** Most modern harnesses (Claude Code, Cursor, Windsurf, IDE copilots) speak
MCP. A local proxy sitting between harness and servers records tool traffic for *any* MCP-speaking
platform at once — the cheapest broad-fidelity path — and simultaneously fills the
`mcp-server-events` gap and R9 inventory from live traffic, not just tool names. PRD 11 reserved
proxy interposition for Cursor (B1/DD-15); this generalizes it into the platform strategy.

**Behavior.** An opt-in local MCP proxy mode: `agentwatch init --mcp-proxy` re-points the
harness's MCP servers at the proxy, which forwards (async, non-blocking) and records every
request/response as records with full `tool.server` attribution — same redaction, same chain.

**Data & schema impact.** A new proxy transport speaking MCP JSON-RPC; reuses the adapter's
record construction. Request/response become `tool.arguments`/`tool.response` (I1) and
`tool.server` (D1).

**Security & privacy.** Consent-first (like G3): explicitly installed, never silent; uninstall
restores the original harness config byte-for-byte. The proxy sees full request/response, so the
privacy mode + secrets pipeline are mandatory. Local-only transport.

**Edge cases.** Streaming/large payloads; server errors (record outcome=error like
PostToolUseFailure); concurrent calls; servers that require OAuth (proxy must not break the flow);
plugin-scoped server names; harness config formats differing across platforms. Because conformance
is against the MCP JSON-RPC spec, protocol-level tests cover all harnesses at once.

**Dependencies.** MCP (protocol); adapter/redaction (shipped); D1; I1; G3; O1; J1.

**Testing.** Proxy round-trip records both directions; uninstall restores original config
byte-identically; error responses recorded; JSON-RPC conformance + fuzzing (PRD 18).

**Risks & mitigations.** Breaking a user's MCP setup (consent + byte-identical restore + tests).
Secrets in proxied traffic (mandatory masking). Non-MCP harnesses (fall back to native/OTel).

**Decision.** D-P (opt-in interposition + async forwarding + restore guarantee).

### N2. OTel GenAI ingestion (transcode, don't instrument) · M10 · #213

**Why (evidence).** Not every platform will get (or needs) a native adapter — but any platform
that emits OTel GenAI, or whose exports we can transcode, can still land in the same store,
replay, and evidence pipeline. Ingestion makes agentwatch useful to embedders (P5) with zero code
on their side and is the natural home for "recorded elsewhere, prove it here."

**Behavior.** `agentwatch ingest --format otel|ndjson <source>` validates, normalizes, redacts,
and chains foreign traces into the local store — the same motion as transcript import (H1),
generalized.

**Data & schema impact.** A transcoder mapping OTel GenAI spans/attributes onto our records +
security events; reuses `validate_record`/`validate_event`.

**Security & privacy.** Foreign content is untrusted: run the secrets pipeline and privacy mode
before storage; validate strictly (F8) and quarantine (B4) what does not normalize. No egress —
ingest is local file/stdin.

**Edge cases.** Foreign schemas missing fields → map what exists, report gaps (never invent).
Huge traces → stream. Conflicting ids → namespace by source. Embedded secrets → masked.

**Dependencies.** Records/redaction (shipped); H1 importer; B4; J1.

**Testing.** Ingest a fixture OTel trace → records chain and validate; a secret in foreign
content is masked; unmappable input is quarantined with a reason.

**Risks & mitigations.** Becoming a general OTel backend (D-Q: records + events first). Foreign
data quality (strict validation + quarantine).

**Decision.** D-Q (ingestion scope).

### N3. Fake-harness emitters · M10 · #214

**Why (evidence).** Daemon/pipeline tests should not require real harnesses, real auth, or
network — and hand-written fixtures only cover what we remember. A fake harness exercises
long-running paths (pairing, dedup, gaps, retention) against a realistic stream, per platform
contract, on every PR.

**Behavior.** One small emitter per supported platform generating event streams — including
malformed and out-of-order ones — consumed by daemon tests, soak, and the conformance runner's
negative cases.

**Data & schema impact.** Test utilities (never production — per writing-good-tests, cleanup/test
code lives in test utilities).

**Security & privacy.** Synthetic data only; no real transcripts.

**Edge cases.** Out-of-order Pre/Post (P1); duplicates (F2); malformed frames (B4); clock skew
(B5).

**Dependencies.** O1; F1/F2; P1.

**Testing.** Deterministic streams exercise the long-running paths without a real harness.

**Risks & mitigations.** Emitters drifting from real harness behavior (version-tagged fixtures,
O1/N4).

**Decision.** D-19.37 (which platforms get an emitter first).

### N4. Generated compatibility table + harness version matrix · M10 · #215

**Why (evidence).** PRD 09 promises a compatibility table per release; making it *generated*
keeps it honest. And "tested range" only means something if fixtures are version-tagged and drift
is detected nightly — otherwise we learn from a user.

**Behavior.** Fixtures tagged with harness version; adapters declare a tested min/max range; a
nightly drift job records results and opens an issue on a shape change; the release compatibility
table is generated from the same data.

**Data & schema impact.** Adapter metadata (tested range) + version-tagged fixtures + a generator
for `compatibility.md`.

**Security & privacy.** None.

**Edge cases.** A new harness version that only adds fields (compatible) vs. changes shape
(breaks a fixture). A range with no fixtures.

**Dependencies.** I2 golden corpus; O1; G4 (preflight consumes ranges).

**Testing.** Drift job (simulated harness change) opens an issue; table generated deterministically.

**Risks & mitigations.** Stale ranges (drift job + release gate).

**Decision.** D-19.38 (version-source mechanism).

### O1. Shared adapter conformance runner · M5 · #216

**Why (evidence).** Conformance is currently a Claude Code test file, not a contract. As soon as
a second adapter exists (Cursor, MCP proxy, community), "each adapter meets the same bar" must be
mechanical, not aspirational — otherwise the second adapter ships weaker than the first and the
parity story erodes.

**Behavior.** A reusable runner every adapter registers into, blocking in CI. It enforces:
fixture replay; capability/gap disjointness; explicit rejection of declared gaps; record
validation on every output; and dedup/idempotency behavior.

**Data & schema impact.** `tests/conformance/` runner + per-adapter registrations; the runner is
the plugin contract for community adapters (J1).

**Security & privacy.** A conformance failure blocks merge (quality gate).

**Edge cases.** An adapter with no conformance registration → CI fails. A deliberately broken
sample adapter → runner fails (proves the gate works).

**Dependencies.** Adapter interface (shipped); J1; N3 fake harness; N4 ranges.

**Testing.** A deliberately broken sample adapter fails conformance; every shipped adapter
passes.

**Risks & mitigations.** Runner too strict for legitimate differences (capability/gap mechanism
absorbs them).

**Decision.** D-R (blocking CI gate for every adapter, community included).


### I2. Golden corpus of real harness events · M8 · #199

**Why (evidence).** Our conformance fixtures are hand-written. We were already bitten in M3 by
harness-doc drift (our illustrative hook JSON was outdated); the same drift will happen again,
silently, unless real events keep us honest. This is the CI tripwire for "Claude Code changed
underneath us."

**Behavior.** The pending authenticated live-run (the M3 #159 follow-up) becomes a capture
harness: a recorded corpus of *real* hook events, committed as fixtures tagged with the harness
version, replayed against the adapter in CI. When the harness event shape changes, a fixture
fails instead of a user.

**Data & schema impact.** `tests/fixtures/**/golden/` tagged by harness version; a capture script
(run with an authenticated harness, off the critical path).

**Security & privacy.** Captured events may contain real tool args/response content — scrub them
through the privacy pipeline before committing (or synthesize from the real *shape* when values
are sensitive). Fixtures must contain no real secret or PII (governance gate).

**Edge cases.** A harness version that adds fields (fixture still passes) vs. changes/removes one
(breaks). A capture run with no auth (the current environment) → tests skip with a clear reason;
the corpus is refreshed on an authenticated machine. Scrub/review before commit.

**Dependencies.** Adapter (shipped); N4 version matrix; O1 runner; the #159 authenticated run.

**Testing.** CI replay fails when the harness event shape changes; fixtures contain no secrets
(automated scan).

**Risks & mitigations.** Committing real sensitive data (scrub + scan + review). Stale corpus
(version tags + nightly drift, N4).

**Decision.** D-19.39 (scrub-and-commit vs. synthesize-from-shape).

