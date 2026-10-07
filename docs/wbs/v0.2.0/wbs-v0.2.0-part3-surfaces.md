# WBS v0.2.0 — Part 3: Surfaces (M27)

**BLUF:** M27 widens the capture surface: the MCP 2026-07-28 protocol work, Codex + long-tail log readers, the
Claude Compliance API, LLM telemetry upgrades, detector telemetry, the SIEM/OCSF stream, LangGraph/raw-Python
Tier-2, Windows, the examples gallery, and cross-parser validation.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **WBS updated** · **issues updated** · **code committed and pushed to
> `feat-v0.2.0`** · design docs updated.

---

## Milestone M27 — Surfaces (PRD 42–47)

**Status:** 🚧 **in progress** (2026-10-06) — **done (26):** MCP-1..6 (#333–#338), GEM-2 (#342), DET-4 (#343,
LLM numbers published), DET-5 (#344), COR-2 (#345), SIEM-1/2 (#346/#347), LG-1 (#348, O1 SDK pack), LG-2 (#349),
EXA-1 (#351), COD-1 (#339), XHT-3 (#352), LOG-1 (#340) (unblocked by downloading the verified Codex format, two
pinned OSS parsers, and the OpenCode SDK schema), CCA-1 (#341, Compliance API ingest), UI-2 (#431), A11Y-1 (#432),
RUN-1 (#433), TUT-1 (#434), 27.T (#377), 27.D (#378). **Blocked (declared):** WIN-1 (#350, needs a Windows host).
Milestone gate (`make test`: SDK/API/analytics ≥95%, repo guard 34; `ruff`/`mypy`/web clean) run; 27.R open.

**Goal:** Reach real harnesses across the long tail and every MCP surface, harden the SOC feed, and open the
Tier-2 framework and Windows lanes.

**Requirements / PRDs:** [PRD 42](../../prd/42-harness-fidelity-and-realtime.md) · [PRD 43](../../prd/43-detector-credibility-and-evaluation.md) ·
[PRD 44](../../prd/44-identity-enterprise-and-compliance.md) · [PRD 45](../../prd/45-new-capture-surfaces.md) ·
[PRD 46](../../prd/46-platform-sdk-and-growth.md) · [PRD 47](../../prd/47-cross-harness-testkit.md).

**Work items**

| # | Task | Deliverable | Acceptance | Issue |
|---|---|---|---|---|
| 27.MCP-1 | Proxy Streamable HTTP transport (HTTP/SSE kept, marked deprecated-in-spec) | feature + tests | Conformance vs 2026-07-28 fixtures; sessions-removal posture documented | #333 |
| 27.MCP-2 | Record `resources/read` + resource links in tool results | feature + tests | Same redaction/chain/attribution pipeline; `search --mcp-resource` | #334 |
| 27.MCP-3 | Record `prompts/get` | feature + tests | Same pipeline; pairs with prompt-version fingerprints | #335 |
| 27.MCP-4 | Record elicitation request/response; link to approval provenance | feature + tests | Human-input surface provable; `unknown` where not exposed | #336 |
| 27.MCP-5 | Record tasks lifecycle; mark sampling/roots/logging closed-by-spec (SEP-2577) | feature + tests + docs | A per-revision fixture set; the sampling gap leaves known-limitations citing the spec | #337 |
| 27.MCP-6 | Protocol-version conformance matrix (2025-06-18 / 2025-11-25 / 2026-07-28) | matrix + CI | Protocol drift fails CI; compat table gains a protocol column | #338 |
| 27.COD-1 | Codex rollout reader (`.jsonl.zst`, compacted, dangling sessions), dedup (F2) | feature + tests | Fixture-verified against the published format; weaponized fixture contained, never executed | #339 |
| 27.LOG-1 | Long-tail log readers (Copilot, OpenCode transcripts, niche CLIs); `log-read` tier | feature + tests | Read-only; fixture per agent/version; redaction on foreign content; `producer: import` | #340 |
| 27.CCA-1 | Claude Compliance API ingest (consent-first pull) | feature + tests | Explicit opt-in; pulls recorded as `store-access`; feed-vs-hook discrepancies classified, never silently merged | #341 |
| 27.GEM-2 | Gemini attribute mapping (`active_approval_mode`→approval, `user.email`→principal hashed, ids→identity) | feature + tests | Matrix row flips to native-telemetry-ingest; identity hashed by default | #342 |
| 27.DET-4 | LLM detectors upgraded to the eval harness (local-model-first) | feature + tests | Published numbers; no LLM in the trust path | #343 |
| 27.DET-5 | Opt-in local detector telemetry (fired/suppressed/FP markers) | feature + tests | Opt-in; content-free; documented; feedable to SIEM sinks | #344 |
| 27.COR-2 | AIR/AIID (GMF) taxonomy mapping + optional incident tags on `annotate` | feature + tests | Mapping property-tested (every event type has a correspondent or explicit none); tags metadata-only | #345 |
| 27.SIEM-1 | OCSF 1.5.0 event stream conformance-tested; reference consumers per flavor | feature + examples + CI | Consumers green in CI; events-only, bounded; redaction gate blocks an unconfigured sink | #346 |
| 27.SIEM-2 | Syslog sink (opt-in, redaction-gated) | feature + tests | S10 gate applies; `degraded` visible on failure | #347 |
| 27.LG-1 | LangGraph `TracedGraph` full fidelity | feature + conformance pack | One command instruments an app; pack green (O1) | #348 |
| 27.LG-2 | Raw-Python SDK path to the unified store | feature + tests | `source: sdk` distinction preserved (S11) | #349 |
| 27.WIN-1 | Windows: named-pipe transport, service registration, CI leg, matrix column | feature + CI | CUJ-1 passes on Windows ≤ 15 min; Windows CI leg green | #350 |
| 27.EXA-1 | Examples gallery: one CI-executed recipe per integration | examples + CI | All green in CI or explicitly illustrative; claims-ledger entries | #351 |
| 27.XHT-3 | Golden-corpus cross-validation vs two independent OSS parsers | CI job + report | Divergence = failing test; parsers version-pinned; attribution in THIRD_PARTY_NOTICES | #352 |
| 27.UI-2 | Operator UI: identity/attribution, SIEM health, detector telemetry | feature + tests | Attribution + sink health + detector markers rendered | #431 |
| 27.A11Y-1 | Accessibility (axe + WCAG 2.2 AA) for new UI views | tests + CI | axe per new view; keyboard journey extended | #432 |
| 27.RUN-1 | Runbooks: Cursor/Gemini/Codex install+verify, OCSF/SIEM export, MCP full-surface | docs | Runbooks authored and linked | #433 |
| 27.TUT-1 | Tutorials: Cursor, Gemini, AAT mapping, cross-harness testing | docs | Tutorials authored; commands CI-executed where automatable | #434 |
| 27.T | Add/expand test cases for this milestone | tests | All new paths covered; coverage ≥ 95% | #377 |
| 27.D | Create/update the design + reference docs for this milestone | docs | Docs updated and linked from the WBS | #378 |
| 27.R | Code review & risk sign-off for this milestone | review | Review recorded; no unresolved findings | #379 |

**Tests required:** three-revision MCP fixture suite; reader fixtures per agent/version; SIEM reference consumers;
LangGraph conformance; Windows leg; cross-parser diff; coverage ≥ 95% on all new modules.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · WBS + issues updated · pushed to `feat-v0.2.0`
- [ ] **All relevant documents are updated as the milestone is closed out** (see "Documents to update at
      close-out" below)
- [ ] MCP resources/prompts/elicitation/tasks recorded; Codex/long-tail readers fixture-verified; SIEM consumers
      green; LangGraph + Windows lanes live; no unregistered capture path.
- [ ] Content gates: known-limitations G5 (modeled rows) and G6 (MCP surface) leave with proving tests; matrix rows
      re-tiered; claims-ledger entries.

**Documents to update at close-out:** the design docs listed below, plus [PRD 42](../../prd/42-harness-fidelity-and-realtime.md),
[PRD 43](../../prd/43-detector-credibility-and-evaluation.md), [PRD 44](../../prd/44-identity-enterprise-and-compliance.md),
[PRD 45](../../prd/45-new-capture-surfaces.md), [PRD 46](../../prd/46-platform-sdk-and-growth.md),
[reference/compatibility.md](../../reference/compatibility.md), [reference/known-limitations.md](../../reference/known-limitations.md),
[CHANGELOG](../../../CHANGELOG.md), [README](../../../README.md).

**Design docs to update:** [mcp-surface.md](../../design/mcp-surface.md) · [harness-adapter-design.md](../../design/harness-adapter-design.md) ·
[detector-evaluation.md](../../design/detector-evaluation.md) · [observability.md](../../design/observability.md) ·
[cross-harness-testing.md](../../design/cross-harness-testing.md).

---
