# WBS v0.2.0 — Part 6: Expanded II — Code, Capabilities, Console & Investigation (M30)

**BLUF:** M30 lands the expanded product-depth work: the **capability supply chain** (skills/plugins/hooks/rules/memory),
**code provenance** (Agent Trace), the **zero-Docker local console + embedded query tier**, **agent-facing interfaces**,
**policy-from-history**, the deeper **investigation** surfaces (environment diff, cases, concurrency, browser verifier,
sandbox events), **outcomes + ephemeral capture**, the **redaction benchmark**, and growth motions. It runs after M29 and
before the last two milestones, [M31 Field Tests + M32 Release Readiness](wbs-v0.2.0-part7-field-test-release.md).

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **WBS updated** · **issues updated** · **all relevant documents updated as the
> milestone is closed out** · **code committed and pushed to `feat-v0.2.0`** · design docs updated.

---

## Milestone M30 — Expanded II: Code, Capabilities, Console & Investigation (PRD 52–55, 57–58)

**Status:** 🔄 in progress — PRV-3 (#464), PRV-1 (#462), PRV-2 (#463), CNC-1 (#474), OUT-1 (#477) landed on `m30-ws2`

**Goal:** Close the credibility and usefulness gaps around the record: inventory and diff everything the agent can load,
connect sessions to the code they produced, give the hook store a first-minute browser view and a fast query tier, expose
the record to agents safely and turn history into advisory policy, and deepen investigation/outcomes — still monitor-only,
local-first, redact-before-store, no LLM in the trust path.

**Requirements / PRDs:** [PRD 52](../../prd/52-capability-supply-chain-and-memory.md) ·
[PRD 53](../../prd/53-code-provenance-and-attribution.md) ·
[PRD 54](../../prd/54-local-console-and-query-tier.md) ·
[PRD 55](../../prd/55-agent-interfaces-and-policy-from-history.md) ·
[PRD 57](../../prd/57-investigation-depth-and-verification.md) ·
[PRD 58](../../prd/58-outcomes-ephemeral-capture-and-growth.md) · [PRD 40](../../prd/40-v0.2.0-program.md) ·
[PRD 48](../../prd/48-v0.2.0-risks-testing-and-decisions.md).

**Work items**

| # | Task | Deliverable | Dependencies | Acceptance | Issue |
|---|---|---|---|---|---|
| 30.CAP-1 | Capability inventory: skills/plugins/hooks/subagents/commands/rules/MCP with content digests + origin | feature + tests + docs | PRD 25, S4 | Content digest (not pin) recorded; no content stored (property test); per-harness gaps declared | #458 |
| 30.CAP-2 | Capability drift + `capability-changed` event | feature + schema + tests | 30.CAP-1, 29.EXT-3 | Plugin4Shell-shape fixture ("content changed, version unchanged") detected; new hook surfaced; no verdict language | #459 |
| 30.CAP-3 | `capability-loaded` context in replay/impact/search | feature + tests | 30.CAP-1, 29.DEP-2 | Loads shown inline; `search --capability` works; per-harness exposure matrix CI-checked; "followed the load of" wording | #460 |
| 30.MEM-1 | Memory stores as capabilities (digest, writer-session) + `search --memory` | feature + tests | 30.CAP-1, 28.DET-7 | Out-of-band memory edit flagged unattributed; per-harness exposure matrix published | #461 |
| 30.PRV-1 DONE | `provenance <commit|range|PR|file>` | feature + tests | 30.PRV-3, 29.APV-1 | Commit→session <2 s; "no recorded activity" when none (never "human"); `mixed` ranges correct; gaps flagged | #462 |
| 30.PRV-2 DONE | Agent Trace export + git-ai notes cross-validation; spec pin + drift job | feature + tests + CI | 30.PRV-1 | Export validates against the pinned revision; zero code content in output; agree/disagree reported; write-to-repo only by explicit command | #463 |
| 30.PRV-3 DONE | Content-free range+hash capture (+ ADR) | feature + property test | 29.DEP-3, privacy review | Under `metadata-only`, ranges+hashes exist and no content/diff does; fallback to file-level `heuristic` documented | #464 |
| 30.LUI-1 | `agentwatch ui` read-only loopback console | feature + tests | 30.LUI-2, 25.STR-1 | Clean install → browser view ≤60 s, no Docker; loopback+token+read-only+no egress; UI=CLI parity; gaps rendered | #465 |
| 30.LUI-2 | Embedded rebuildable query index (+ optional parquet export) | feature + CI + ADR | ADR-0019 | Delete index → works + rebuilds bit-for-bit; interactive search on 1M records; no heavyweight dep without ADR | #466 |
| 30.AGI-1 | Read-only MCP server over the record | feature + tests | 29.APV-1, S21 | Read-only tool set enumerated by test; untrusted labeling + citations; injection fuzz holds; queries recorded as `store-access` | #467 |
| 30.AGI-2 | Investigation skill + versioned CLI JSON schemas | feature + skill + docs | 30.AGI-1 | Scripted agent reaches documented answers on the demo store; JSON schemas changelog-guarded | #468 |
| 30.POL-1 | `suggest-policy` + dangerous-broad lint | feature + tests | 29.APV-1, cls1 | No write outside `--out`; each rule evidence-linked; destructive/network/credential never allow-by-default; deterministic | #469 |
| 30.POL-2 | `what-if` policy replay over history | feature + tests | 30.POL-1 | Prompts-avoided + would-be denials with sessions; parse errors explicit; labeled simulation; format-version stamp | #470 |
| 30.RED-1 | Public redaction corpus + `redact eval` + published per-class numbers | feature + corpus + docs | PRD 43 pattern | Reproduces published numbers deterministically offline; misses in known-limitations; corpus secret-scanned | #471 |
| 30.ENV-1 | Environment fingerprint + delta in `diff`/`drift`; `sessions --group-by-env` | feature + tests | 30.CAP-1, 29.APV-2, 29.CCO-1 | Seeded model change surfaces first; "coincides with" wording; digests only | #472 |
| 30.IR-1 | Incident cases + merged timeline + case bundle | feature + tests | 28.COR-3, 26.TRACE-2 | Membership changes chain-recorded; gaps classified; bundle verifies offline; no registry egress | #473 |
| 30.CNC-1 DONE | Concurrency report + `ambiguous` provenance | feature + tests | 30.PRV-1 | Overlapping sessions + shared-file edits listed; multi-session ranges `ambiguous`; two-session fixture | #474 |
| 30.VFY-1 | Offline browser evidence verifier | feature + artifact + tests | S12 verifier, 29.DEP-2 | Opens from `file://`, zero network; verdicts equal CLI on all fixtures; tampered bundle names the first broken link | #475 |
| 30.SBX-1 | Sandbox-boundary events (verify signals first) | feature + schema + docs | 29.CCO-1, 29.DEP-2 | `% unsandboxed` in `oversight`; attempted-but-blocked destinations separated in `impact`; matrix honest where not exposed | #476 |
| 30.OUT-1 DONE | Deterministic outcome facts + `cost --per retained-change` | feature + tests | EXT-4 (cls2), 30.PRV-1 | Numerator/denominator + derivation version; unknown preserved; runs offline with no model configured | #477 |
| 30.OUT-2 | Recurring failure signatures in `digest`/console | feature + tests | bd1, detectors, 30.LUI-1 | Top-N patterns with counts/trend/evidence links; grouping rules versioned | #478 |
| 30.RUN-1 | Sealed runner segments + `import-segment` + custody label | feature + tests | 26.TRACE-1, S11 | Tampered segment fails; imported records visibly weaker; zero egress; trace join when `traceparent` present | #479 |
| 30.DEMO-1 | Static synthetic demo bundle | docs + artifact | 30.VFY-1 | Opens offline, zero network; synthetic + secret-scanned; linked from README/GTM | #480 |
| 30.NTF-1 | Alert-routing recipes (Slack/PagerDuty/Alertmanager) | docs + CI recipes | EXA-1, SIEM-1, S10 | Three CI-tested recipes; claims-ledger entries; docs state routing stays in the user's stack | #481 |
| 30.EXT-4 | Publish `cls2` (test/build outcome classes); reproduce `cls1` | feature + docs | PRD 33 | `cls2` table published; `cls1` outputs reproducible | #482 |
| 30.EXT-5 | `purge`/retention propagate to every derived index/export; enumerate leftovers | feature + tests | 29.HLD-1, 30.LUI-2 | Post-purge index/console empty; leftover artifacts enumerated | #483 |
| 30.EXT-8 | Re-sequence PG behind LUI-2; record decision | docs + ADR | 30.LUI-2 | ADR records embedded-index-first; PG = fleet/tenant tier | #484 |
| 30.T | Add/expand test cases for this milestone | tests | M30 feature tickets | All new paths covered; coverage ≥ 95% | #485 |
| 30.D | Create/update the design + reference docs for this milestone | docs | M30 feature tickets | Docs updated and linked from the WBS | #486 |
| 30.R | Code review & risk sign-off for this milestone | review | M30 feature tickets + 30.T + 30.D | Review recorded; no unresolved findings | #487 |

> **Issues filed:** #458–#487, under the **M30** GitHub milestone
> ([milestones](https://github.com/agentsec-ecosystem/agentwatch/milestones)).

**Tests required:** capability-drift + load-attribution fixtures; memory out-of-band edit; provenance resolution + mixed
ranges + Agent Trace differential vs git-ai notes; range/hash content-free property test; console security + UI/CLI
parity + index rebuild; MCP read-only enumeration + injection fuzz; policy-suggestion no-write + determinism +
what-if numbers; redaction-eval reproduction; environment-delta fixture; case bundle verify; concurrency fixture;
browser-verifier differential; sandbox-event fixtures (where exposed); outcome determinism; runner-segment tamper;
demo/recipe executable docs. Plus fuzz/property/mutation extensions for the new parsers and trust-path mutants.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · WBS + issues updated · **all relevant documents updated** · pushed
- [ ] Plugin4Shell-shape drift detected; commit→session resolves; Agent Trace validates; console ≤60 s with no Docker and
      UI=CLI parity; MCP server read-only + fuzz-safe; `suggest-policy`/`what-if` write nothing outside `--out`; redaction
      numbers reproducible; case bundle verifies offline; runner segment tamper fails; index rebuild bit-for-bit
- [ ] Design docs updated: [capability-supply-chain](../../design/capability-supply-chain.md),
      [code-provenance](../../design/code-provenance.md), [local-console](../../design/local-console.md),
      [agent-interfaces](../../design/agent-interfaces.md), [policy-from-history](../../design/policy-from-history.md),
      [environment-fingerprint](../../design/environment-fingerprint.md),
      [browser-verifier](../../design/browser-verifier.md), [runner-segments](../../design/runner-segments.md),
      [outcomes-signals](../../design/outcomes-signals.md)

**Documents to update at close-out:** the design docs above; [PRD 52](../../prd/52-capability-supply-chain-and-memory.md),
[PRD 53](../../prd/53-code-provenance-and-attribution.md),
[PRD 54](../../prd/54-local-console-and-query-tier.md),
[PRD 55](../../prd/55-agent-interfaces-and-policy-from-history.md),
[PRD 57](../../prd/57-investigation-depth-and-verification.md),
[PRD 58](../../prd/58-outcomes-ephemeral-capture-and-growth.md);
[reference/record-format-spec.md](../../reference/record-format-spec.md),
[reference/store-format.md](../../reference/store-format.md),
[reference/compatibility.md](../../reference/compatibility.md),
[reference/known-limitations.md](../../reference/known-limitations.md),
[reference/evidence-verifier.md](../../reference/evidence-verifier.md),
[design/derived-postgres.md](../../design/derived-postgres.md), [CHANGELOG](../../../CHANGELOG.md).

---
