# WBS v0.1.0 — Part 4: Analytics, Detectors, API & UI (M6–M7)

**BLUF:** Adapt the **ported** analytics service and 40 detectors, then the read API and operator UI — the
bulk of the shipped-feature parity. Two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M6 — Analytics + detector engine

**Status:** ✅ **implemented** — the ported analytics service satisfies 6.1–6.9 (706 tests, coverage
97.79%): trace-ingestion poller, run-summary materialization, fleet rollup + version cohorts, 35
rule detectors (+5 LLM, default off), Postgres schema + Alembic migration, and 30 configurable
threshold settings. Additions: `tool.response` capture (#198) and the Claude Code detector pack
(#210: `write-storm`, `denied-cluster`, `network-tool`; 38 detectors registered).

**Goal:** adapt the **ported** analytics pipeline (ingestion, run summaries, fleet rollup, version cohorts,
thresholds) and the **40 detectors** (35 rule + 5 LLM), backed by Postgres.

**Requirements / PRDs:** parity A2/A3 ([PRD 10](../../prd/10-feature-parity.md)),
[data dictionary](../../design/data-dictionary.md), [detector catalog](../../reference/detector-catalog.md),
[observability](../../design/observability.md).

**Work items (port first)**

| # | Task | Deliverable | Acceptance | Issue | Issue |
|---|---|---|---|---|---|
| 6.1 | **Port/adapt** trace-ingestion poller | ingestion | traces consumed from Jaeger/Tempo | #47 |
| 6.2 | **Port/adapt** run-summary materialization | summaries | per-run aggregates correct | #48 |
| 6.3 | **Port/adapt** fleet rollup + version-cohort summaries | rollups | cohort deltas computable | #49 |
| 6.4 | **Port/adapt** 35 rule-based detectors | detectors | all classes registered | #50 |
| 6.5 | **Port/adapt** 5 LLM detectors (feature-flagged, default off) | LLM detectors | flagged + off | #51 |
| 6.6 | Postgres schema + migrations (data dictionary) | schema | migrations apply cleanly | #52 |
| 6.7 | Configurable thresholds per detector/workload | config | thresholds honored | #53 |
| 6.8 | Corpus + detector tests | tests | fire/no-fire fixtures green | #54 |
| 6.9 | **Update design docs** | data-dictionary, detector-catalog, observability | docs match implementation | #55 |
| 6.T | Add/expand test cases for this milestone (unit + integration + fault-injection) | tests | all new paths covered; coverage ≥ 95% | #125 |
| 6.D | Create/update the design + reference docs for this milestone | docs | docs updated and linked from the WBS | #126 |

**Tests required:** ingestion → run summary; fleet rollup + cohort math; 40 detectors (fire/no-fire corpus);
threshold configurability; migration up/down.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] Run summaries, fleet rollups, and cohort deltas computed correctly (parity A3)
- [ ] **40 detectors** registered + corpus tests green (parity A2)
- [ ] Postgres schema + migrations clean

**Design docs to update:** [data-dictionary.md](../../design/data-dictionary.md),
[detector-catalog.md](../../reference/detector-catalog.md), [observability.md](../../design/observability.md),
[known-limitations.md](../../reference/known-limitations.md), [CHANGELOG](../../../CHANGELOG.md).

**Additions (PRD 19–30) landing in M6**

| # | Addition | Deliverable | Acceptance | PRD | Issue |
|---|---|---|---|---|---|
| 6.A5 | Cost rollup from tokens + model | pricing table + rollup | per-run/agent cost computed | [20](../../prd/20-usage-accounting.md) | #169 |
| 6.I1 | Tool responses (both directions) | additive `tool.response` | mode-gated; secret-masked; schema contract | [25](../../prd/25-capture-fidelity.md) | #198 |
| 6.L1 | Claude-Code detector starter pack | rule detectors | fire/no-fire fixtures; signals only | [30](../../prd/30-analytics-signals.md) | #210 |

---

## Milestone M7 — Read API + operator UI

**Status:** ✅ **implemented** — ported FastAPI read API (`/runs`, `/runs/{id}`, `/fleet`, `/compare`,
`/anomalies`; 42 tests) and the React/Vite operator UI (five views + 34 Playwright cases) are in
place. Additions: `agentwatch view` terminal timeline (#195) and `agentwatch explain` deterministic,
local-first summary (#211). A11y baseline automated: axe checks for all five views live in
`apps/web/src/__tests__/a11y.test.tsx` (#63). E2E not run green here (Docker daemon unavailable).

**Goal:** adapt the **ported** FastAPI read API and React operator UI (Fleet Health, Run Timeline, Version
Compare, Anomaly Inbox, Agent Detail) wired to analytics.

**Requirements / PRDs:** parity A4/A5 ([PRD 10](../../prd/10-feature-parity.md)),
[API reference](../../reference/api.md), [UI accessibility](../../design/ui-accessibility.md),
[UI interaction observability](../../design/ui-interaction-observability.md).

**Work items (port first)**

| # | Task | Deliverable | Acceptance | Issue | Issue |
|---|---|---|---|---|---|
| 7.1 | **Port/adapt** FastAPI read API (`/runs`, `/runs/{id}`, `/fleet`, `/compare`, `/anomalies`) | read API | contract shapes preserved | #56 |
| 7.2 | **Port/adapt** React UI scaffold (Vite) | web app | builds + serves | #57 |
| 7.3 | **Port/adapt** Fleet Health view | view | agent cohorts + anomaly counts | #58 |
| 7.4 | **Port/adapt** Run Timeline view | view | span tree + anomaly markers | #59 |
| 7.5 | **Port/adapt** Version Compare view | view | side-by-side deltas | #60 |
| 7.6 | **Port/adapt** Anomaly Inbox view | view | triage by severity/type/agent | #61 |
| 7.7 | **Port/adapt** Agent Detail view | view | metrics, tool mix, cost trend | #62 |
| 7.8 | Wire UI ↔ API; a11y baseline | integration | keyboard + contrast pass | #63 |
| 7.9 | **Update design docs** | api, ui-accessibility, ui-interaction-observability | docs match UI/API | #64 |
| 7.T | Add/expand test cases for this milestone (unit + integration + fault-injection) | tests | all new paths covered; coverage ≥ 95% | #127 |
| 7.D | Create/update the design + reference docs for this milestone | docs | docs updated and linked from the WBS | #128 |

**Tests required:** API contract tests (all five endpoints); UI build; view render tests; basic a11y checks.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] All five read-API endpoints return preserved shapes (parity A4)
- [ ] All five operator views render against seeded data (parity A5)
- [ ] Basic accessibility baseline met

**Design docs to update:** [api.md](../../reference/api.md), [ui-accessibility.md](../../design/ui-accessibility.md),
[ui-interaction-observability.md](../../design/ui-interaction-observability.md), [comparison.md](../../reference/comparison.md),
[CHANGELOG](../../../CHANGELOG.md).

**Additions (PRD 19–30) landing in M7**

| # | Addition | Deliverable | Acceptance | PRD | Issue |
|---|---|---|---|---|---|
| 7.H4 | `agentwatch view` — terminal timeline (R12) | stdlib-curses TUI | renders fixture store; non-TTY fallback | [26](../../prd/26-investigation.md) | #195 |
| 7.M1 | LLM `explain` (local-first; stretch) | explain command | citations; no egress by default; deterministic summary | [29](../../prd/29-llm-explanation.md) | #211 |

---

Part 4 green ⇒ proceed to [Part 5 (M8–M9)](wbs-v0.1.0-part5-stack-inventory.md).
