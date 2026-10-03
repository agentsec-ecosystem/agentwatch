# WBS v0.1.0 — Part 11: Content-Flow Forensics & Capture Context (M18–M19)

**BLUF:** Record deterministic data-flow facts and complete the record's context. PRDs 31–39, all in v0.1.0. Field Tests (M23) and Release Readiness (M24) remain the last two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M18 — Content-Flow Forensics (PRD 34)

**Status:** ☐ not started

**Goal:** Record deterministic data-flow facts: untrusted content to argument flow, and tracing an exposed secret across a session.

**Requirements / PRDs:** [PRD 34](../../prd/34-content-flow-forensics.md) · full detail in the PRD sections.

**Work items**

| # | Task | Deliverable | Acceptance | Issue |
|---|---|---|---|---|
| 18.S22 | Untrusted content → argument flow capture | feature + tests | A fixture where a fetched page's text reappears in a later shell argument produces one | #253 |
| 18.S23 | Trace an exposed secret across the session | feature + tests | A secret detected then echoed into a network tool yields `rotate: recommended` with the path | #254 |

**Tests required:** per-item tests as listed; all new paths covered; coverage ≥ 95%.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated
- [ ] A `content-flow` edge is recorded without content; secret exposure path reported without values.

**Design docs to update:** [PRD 34](../../prd/34-content-flow-forensics.md), [PRD 25](../../prd/25-capture-fidelity.md)

---

## Milestone M19 — Capture Context (PRD 35)

**Status:** ☐ not started

**Goal:** Complete the record's context: approval provenance, context compaction, the VCS revision acted on, the OS principal, and a one-command demo.

**Requirements / PRDs:** [PRD 35](../../prd/35-capture-context.md) · full detail in the PRD sections.

**Work items**

| # | Task | Deliverable | Acceptance | Issue |
|---|---|---|---|---|
| 19.S14 | Approval provenance — record *who authorized* each call | feature + tests | A prompt-then-proceed fixture yields `user` | #255 |
| 19.S15 | Capture context compaction | feature + tests | A `PreCompact` event yields one `context-compacted` step with the trigger | #256 |
| 19.S16 | Capture the revision the agent acted on | feature + tests | A git fixture records SHA/branch/dirty | #257 |
| 19.S29 | Capture the OS principal | feature + tests | A simulated CI env classifies `ci` | #258 |
| 19.S31 | `agentwatch demo` — prove the pipeline in 30 seconds | feature + tests | `demo` records chain and verify | #259 |

**Tests required:** per-item tests as listed; all new paths covered; coverage ≥ 95%.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated
- [ ] Approval defaults to `unknown` where unexposed; session-start snapshot never blocks; `demo` self-cleans.

**Design docs to update:** [PRD 35](../../prd/35-capture-context.md), [PRD 19](../../prd/19-agent-lifecycle.md), [record-format spec](../../reference/record-format-spec.md)

---
