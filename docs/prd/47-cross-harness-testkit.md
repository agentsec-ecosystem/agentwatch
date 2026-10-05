# PRD 47 — Cross-Harness Test Kit

**BLUF:** Make harness compatibility **provable without owning any proprietary CLI**: a public, version-tagged
corpus of real-shaped hook payloads and transcript/rollout fixtures with a replay runner wired into the O1
conformance suite; a live soak on **OpenCode** (MIT, provider-agnostic) as a free real-agent stand-in; golden-corpus
cross-validation against independent OSS parsers; and honest **fidelity tiers**
(`live-verified | fixture-verified | modeled`) in the generated compatibility matrix.

**Status:** proposed v0.2.0 (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M25–M27 ·
**M25 subset implemented:** XHT-1 (corpus under `tests/testkit/` + replay/self-test) and XHT-4 (fidelity tiers).
**Depends on:** PRD 27 (Conformance runner, fake-harness emitters, version matrix), PRD 38 · **Extends:** PRD 27

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only,
> every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency
> without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **compatibility testing for a recorder is fixture-driven conformance** — the CLIs are the source of
*shape*, not the test harness. Claude Code and Cursor both pipe JSON to stdin hooks (so a payload replay is the
officially documented test pattern); Codex rollouts and Claude transcripts are documented file formats; OpenCode is
a real, free, hook-compatible agent.

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| XHT-1 | Public payload/transcript corpus + replay runner | verify an adapter with no CLI; contributors/CI need it | CUJ-1 (adapted), CUJ-19 |
| XHT-2 | Live soak on OpenCode (real agent, free, CI) | synthetic emitters miss real-harness unknowns; adds a free harness row | CUJ-1/17 |
| XHT-3 | Cross-validate vs 2 independent OSS parsers | our format knowledge pinned against our own fixtures | CUJ-1 |
| XHT-4 | Honest fidelity tiers in the matrix | "modeled" hides two truths; honesty is the differentiator | all |

**The "how" lives in design docs:** corpus layout, runner integration, and tier semantics in
[`design/cross-harness-testing.md`](../design/cross-harness-testing.md) (including the practical
"test without owning the CLI" recipes); raw OSS provenance in
[`reference/v0.2.0-research-sources.md`](../reference/v0.2.0-research-sources.md) §9; harness contracts in
[`design/harness-adapter-design.md`](../design/harness-adapter-design.md).

### XHT-1. Harness payload corpus + replay runner · v0.2.0 · (new)

**Why.** PRD 27 defined the conformance runner (O1) and fake-harness emitters (N3) but the fixtures are
hand-written; and teams that do not use a given CLI (us, contributors, CI) cannot verify an adapter. A public
payload/transcript corpus plus a replay runner makes adapter verification mechanical and possible without the CLI.

**Behavior.** A version-tagged corpus (Claude Code all hook events incl. `SubagentStart/Stop`, `PreCompact`,
`PostToolUseFailure`, `transcript_path`; Cursor `before*/after*` events incl. blocking shapes and IDE/CLI/remote env
variants; Codex rollouts incl. `.jsonl.zst`, `compacted` replacement-history, dangling sessions; Gemini OTel
telemetry; OpenCode `tool.execute.*`; Copilot session events) + a replay runner (`agentwatch replay-fixtures` or an
O1 pytest entry) that pipes each payload through the adapter/daemon and asserts the canonical record output. Seed
fixtures from published docs, OSS projects' test data, and consented captures (I2 scrub-and-commit).

**Data & schema impact.** Test assets + runner; no product change.

**Security & privacy.** Every fixture passes the secret scan; no real secrets/PII (governance gate).

**Edge cases.** Ordering/duplicate/malformed variants included (fake_harness emitter behaviors); a broken adapter →
the runner fails.

**Dependencies.** PRD 27 (O1, N3, N4, I2), PRD 42, PRD 45 (LOG-1).

**Testing.** `replay-fixtures --self-test` proves a deliberately broken adapter fails; every registered adapter
ships ≥N fixtures.

**Risks & mitigations.** Fixture rot → version tags + nightly drift (N4); license contamination → recorded sources
+ `THIRD_PARTY_NOTICES`.

**Decision.** ADR (XHT) — corpus licensing + minimum-fixtures-per-adapter rule.

### XHT-2. Live soak on OpenCode · v0.2.0 · (new)

**Why.** Synthetic emitters cannot find a real harness's unknown-unknowns (timing, payload quirks, long sessions,
compaction). OpenCode (MIT, ~180k stars, provider-agnostic — runs local/cheap models) exposes the same modern hook
surface as the proprietary CLIs (`tool.execute.before/after` covering bash/read/write/MCP, `session.created/idle`,
`file.changed` via plugins).

**Behavior.** A nightly/CI stage running OpenCode in a scratch repo with our recorder attached via its plugin hooks,
exercising the full hook→daemon→store→verify→evidence pipeline for hours — alongside the synthetic fake_harness
soak, not replacing it. OpenCode becomes a supported harness row (its universal tool hook maps 1:1 to our
adapter contract).

**Data & schema impact.** New adapter row; discovered quirks feed XHT-1.

**Security & privacy.** Hermetic CI (no egress beyond a pinned model endpoint, or fully offline with a local model).

**Edge cases.** Model unavailable → the synthetic soak still runs; a discovered quirk → a fixture by morning.

**Dependencies.** PRD 27 (N3/O1), PRD 46 (CI), XHT-1.

**Testing.** 24 h soak green; matrix row gains `live-verified`.

**Risks & mitigations.** Non-determinism in a real agent → fixed model config + hermetic run.

**Decision.** D-47.x — CI model pinning.

### XHT-3. Golden-corpus cross-validation vs independent parsers · v0.2.0 · (new)

**Why.** Our understanding of the file formats has been pinned against our own fixtures; independent OSS parsers
encode other teams' hard-won format knowledge (`.jsonl.zst` handling, dangling-session heuristics, plaintext
duplication). Cross-checking catches misreads cheaply — the M14 Q6 two-implementation discipline applied to
adapters.

**Behavior.** CI runs our reader and **two independent OSS parsers** (e.g. agent-history, codex-claude-transfer,
agent-ouija) over the same golden fixtures and diffs the normalized output; divergence is a failing test (or a
documented interpretation gap).

**Data & schema impact.** CI job + committed baseline.

**Security & privacy.** Parsers pinned by version; attribution recorded (THIRD_PARTY_NOTICES).

**Edge cases.** A legitimate interpretation difference → documented, not silently absorbed.

**Dependencies.** COD-1, LOG-1, XHT-1.

**Testing.** Cross-parse diff report generated with a baseline; divergence fails.

**Decision.** D-47.y — which independent parsers are the reference pair.

### XHT-4. Compatibility-matrix fidelity tiers · v0.2.0 · (new)

**Why.** "Modeled" collapses two different truths (we know the shape from public fixtures vs we guessed). Splitting
the tier makes the matrix *more* honest exactly when we gain fixture confidence, and prevents marketing pressure
from blurring fixture-verified into full. Known-limitations discipline applied to the matrix.

**Behavior.** Extend `agentwatch.compatibility` + the generated matrix (N4) with a `live-verified | fixture-verified
| modeled` tier per row; a `full`/`live-verified` claim requires a live-capture reference; the generator emits the
tier with corpus citations.

**Data & schema impact.** Matrix generator + docs; no record change.

**Security & privacy.** None.

**Edge cases.** A row with only fixture evidence → `fixture-verified`, never `full`; a closed harness (Cursor) →
stated as fixture-verified until captured live.

**Dependencies.** N4 generator, XHT-1, PRD 42.

**Testing.** Generator emits the tier column; claims-ledger entries for tier statements.

**Risks & mitigations.** Blurred tiers → generator enforcement + claims ledger.

**Decision.** D-47.z — tier vocabulary + promotion criteria.
