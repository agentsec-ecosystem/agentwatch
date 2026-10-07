# WBS v0.2.0 — Part 5: Expanded I — Trust, Identity & Governance (M29)

**BLUF:** M29 lands the expanded trust-and-reach work: truthful **authorization/oversight** provenance, **enterprise
deployability + recorder attestation**, **harness-native telemetry** and framework reach, **fleet access & governance**,
**legal hold**, and the **OWASP Agentic** coverage map. It runs after the implementation milestones M25–M28 and before
the last two milestones, [M31 Field Tests + M32 Release Readiness](wbs-v0.2.0-part7-field-test-release.md).

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **WBS updated** · **issues updated** · **all relevant documents updated as the
> milestone is closed out** · **code committed and pushed to `feat-v0.2.0`** · design docs updated.

---

## Milestone M29 — Expanded I: Trust, Identity & Governance (PRD 49–51, 56, 59)

**Status:** 🔄 in progress — APV-1/APV-2/APV-3/CCO-1/CCO-2 landed on `m29/telemetry-auth` (2026-10-06);
DEP/FWK/ACC/HLD/ASI/STD/EXT tickets pending on their own branches.

> **Progress (2026-10-06, branch `m29/telemetry-auth`):** authorization provenance v2 (`authz-v2` +
> read-time legacy mapping), permission mode per call + transitions, the `oversight` report, Claude Code
> native OTel ingest + `tool_use_id` join, and the Claude Agent SDK/headless path (`source: sdk-native`),
> with design docs, schema changelog, claims-ledger entries, O1 conformance packs, and a generated
> framework-matrix row updated. Full-suite/coverage/ruff/mypy gate run once at the end of this branch.
**Status:** ⏳ in progress — **29.ACC-1 (#448), 29.ACC-2 (#449), 29.HLD-1 (#450) implemented** on
`m29/governance` (WS-C). HLD-1 derived-index propagation is **BLOCKED on 30.EXT-5** (declared).

**Progress:** ACC-1 — role × data-class read model + self-visible access log (`agentwatch.access`,
`agentwatch access log/check/matrix`), ADR-0040; tests `packages/python-sdk/tests/test_access.py`.
ACC-2 — `agentwatch governance notice` from the live effective config + DPIA starter
(`agentwatch.governance`, `docs/compliance/dpia-starter.md`); tests
`packages/python-sdk/tests/test_governance_notice.py`.
HLD-1 — legal holds suspend retention/purge with recorded override provenance (`agentwatch.holds`,
`agentwatch hold add/list/release`, `retention apply --dry-run`, `purge --override-reason`),
ADR-0041; tests `packages/python-sdk/tests/test_legal_hold.py`. **BLOCKED:** propagation to every
derived index/export needs 30.EXT-5 / LUI-2 (M30), absent from this branch.

**Goal:** Make the record truthful about authorization and oversight, provable as "on" in managed-policy fleets,
authoritative for cost/decisions via harness-native telemetry, lawfully governable at fleet scale, and citable against
the OWASP Agentic vocabulary — without weakening any v0.1.0 guardrail (monitor-only · local-first · no LLM in the trust
path · redact-before-store).

**Requirements / PRDs:** [PRD 49](../../prd/49-authorization-and-oversight.md) ·
[PRD 50](../../prd/50-deployability-and-recorder-attestation.md) ·
[PRD 51](../../prd/51-harness-native-telemetry-and-framework-reach.md) ·
[PRD 56](../../prd/56-governance-retention-and-redaction-quality.md) ·
[PRD 59](../../prd/59-owasp-agentic-and-standards-coverage.md) · [PRD 40](../../prd/40-v0.2.0-program.md) ·
[PRD 48](../../prd/48-v0.2.0-risks-testing-and-decisions.md).

**Work items**

| # | Task | Deliverable | Dependencies | Acceptance | Issue |
|---|---|---|---|---|---|
| 29.APV-1 | Authorization source taxonomy v2 (`classifier`/`bypass`/`hook`/`rule`/`human-*`) + legacy mapping | schema + feature + fixtures | 29.CCO-1 (authoritative source), 25.SCHEMA-1 | No classifier/bypass approval recorded as `user`; every value has a derivation fixture; `unknown` when unproven | #438 |
| 29.APV-2 | Permission mode per call + transition records | feature + tests | 29.APV-1 | `search --mode bypass` works; default→bypass→default fixture reconstructs; missing mode → `unknown` counted in `coverage` | #439 |
| 29.APV-3 | `oversight` report (+ `digest` + compliance rows) | feature + tests | 29.APV-1/2, cls1 | Destructive × authorization cross-tab in one offline command; matches hand-computed totals; latency only when timestamps exist | #440 |
| 29.DEP-1 | Managed-policy install path (managed hook / org plugin / MDM) + honest `doctor` | feature + docs + tests | WIN-1, fleet (R13) | `doctor` never reports "installed" when policy blocks hooks; tested on a managed-policy fixture; `uninstall` restores or no-ops | #441 |
| 29.DEP-2 | Session-start recorder attestation + `recorder-config-changed` | feature + tests | 29.DEP-1, S5, S2 | Hooks stripped → change observation + classified gap; attestation carries digests/booleans only (property test) | #442 |
| 29.DEP-3 | Publish end-to-end hook wall-clock per OS + budget + CI gate | feature + CI + docs | perf gate (Q4), WIN-1 | macOS/Linux/Windows p50/p99 published and gated; session overhead quoted; a missed budget yields an ADR | #443 |
| 29.CCO-1 | Claude Code OTel ingest (metrics/events/traces) + `tool_use_id` join | feature + tests + fixtures | 29.OTEL-3 (PRD 41), IDN-1 | ≥95% join on the corpus; discrepancies classified; `cost` exact-vs-estimated source-stamped; no prompt content unless harness+mode allow | #444 |
| 29.CCO-2 | Claude Agent SDK / headless via the same path | feature + example + matrix row | 29.CCO-1, EXA-1 | Runnable gallery recipe green in CI; own compatibility-matrix row with a tier | #445 |
| 29.FWK-1 | Certified recipes: ADK, Strands, OpenAI Agents SDK, Claude Agent SDK | recipes + CI + docs | 29.CCO-1, XHT (PRD 47), EXA-1 | Each pinned recipe runs in CI; OTel GenAI + OpenInference attributes mapped; `unmapped` explicit; ≤2 lines / 1 config block per framework | #446 |
| 29.FWK-2 | `agentwatch.instrument()` auto-detect | feature + tests | SDK-1..3 (M25), 29.FWK-1 | Prints detected frameworks and gaps (no silent partial instrumentation); no-op when agentwatch absent; flush-on-exit; idempotent | #447 |
| 29.ACC-1 | Fleet role × data-class access model + self-visible access log | feature + tests | 29.DEP-1, R13, S21 | Cross-role read returns nothing and is `store-access`-recorded; identity resolution recorded; least-privileged default | #448 |
| 29.ACC-2 | `governance notice` + DPIA starter (from effective config) | feature + docs | 29.ACC-1, `config explain` | Every notice statement maps to a config key or guarantee; unbackable claims omitted and listed; counsel-review banner | #449 |
| 29.HLD-1 | Legal hold suspends retention/purge, with override provenance | feature + tests | 28.CMP-3, EXT-5 | Held records survive retention/purge/index rebuild; `purge` fails closed; override needs a reason and is conspicuous | #450 |
| 29.ASI-1 | `compliance report --framework owasp-asi-2026` (+ AST10) | feature + docs + CI | 28.CMP-1/2, 29.APV-3, 29.CAP-1 (M30) | All ten rows present with an evidence command or "not evidenced"; every row's command runs in CI; non-certification statement | #451 |
| 29.STD-1 | Standards participation plan; close DD-05 | governance + docs | schema stewardship, ADR-0027 | DD-05 closed with a decision; ≥1 upstream contribution per target spec tracked as "submitted" in the claims ledger | #452 |
| 29.EXT-3 | Add `capability-changed`, `recorder-config-changed`, mode-transition to the security-event schema + OCSF/CloudEvents mappings | schema + mappings + fixtures | 25.SCHEMA-1 | Schema changelog + governance check pass; mappings + fixtures updated | #453 |
| 29.EXT-7 | Compatibility matrix: managed-policy column + framework rows | generator + docs | 29.DEP-1, 29.FWK-1 | Every row carries an honest tier; managed-policy status shown | #454 |
| 29.T | Add/expand test cases for this milestone | tests | M29 feature tickets | All new paths covered; coverage ≥ 95% | #455 |
| 29.D | Create/update the design + reference docs for this milestone | docs | M29 feature tickets | Docs updated and linked from the WBS | #456 |
| 29.R | Code review & risk sign-off for this milestone | review | M29 feature tickets + 29.T + 29.D | Review recorded; no unresolved findings | #457 |

> **Issues filed:** #438–#457, under the **M29** GitHub milestone
> ([milestones](https://github.com/agentsec-ecosystem/agentwatch/milestones)).

**Tests required:** authorization-derivation fixtures (every value; no inference from `outcome=ok`); managed-policy
`doctor` fixture; hook-strip attestation; end-to-end hook perf gate on 3 OSes; native-telemetry join + discrepancy
classification; framework recipe conformance; role-matrix denial + access-log; hold-vs-retention/purge/rebuild; ASI
report executable rows. Plus fuzz/property/mutation extensions for the new parsers and the trust-path mutants.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · WBS + issues updated · **all relevant documents updated** · pushed
- [ ] No Claude Code call under auto/bypass reported as `user`; `doctor` truthful under managed policy; attestation
      emitted; hook overhead within budget on macOS/Linux/Windows; ≥95% native-telemetry join; role-matrix denials logged;
      held records survive retention/purge/rebuild; `owasp-asi-2026` every row regenerates
- [ ] Design docs updated: [authorization-provenance-v2](../../design/authorization-provenance-v2.md),
      [recorder-attestation](../../design/recorder-attestation.md),
      [managed-policy-install](../../design/managed-policy-install.md),
      [native-telemetry-join](../../design/native-telemetry-join.md),
      [access-and-governance](../../design/access-and-governance.md), [legal-hold](../../design/legal-hold.md),
      [owasp-asi-mapping](../../design/owasp-asi-mapping.md)

**Documents to update at close-out:** the design docs above; [PRD 49](../../prd/49-authorization-and-oversight.md),
[PRD 50](../../prd/50-deployability-and-recorder-attestation.md),
[PRD 51](../../prd/51-harness-native-telemetry-and-framework-reach.md),
[PRD 56](../../prd/56-governance-retention-and-redaction-quality.md),
[PRD 59](../../prd/59-owasp-agentic-and-standards-coverage.md);
[reference/record-format-spec.md](../../reference/record-format-spec.md),
[reference/compatibility.md](../../reference/compatibility.md),
[reference/known-limitations.md](../../reference/known-limitations.md),
[reference/v0.2.0-research-sources.md](../../reference/v0.2.0-research-sources.md),
[CHANGELOG](../../../CHANGELOG.md).

---
