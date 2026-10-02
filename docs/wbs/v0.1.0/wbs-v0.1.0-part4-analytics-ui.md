# WBS v0.1.0 — Part 4: Analytics, Detectors, API & UI (M6–M7)

**BLUF:** Adapt the **ported** analytics service and 40 detectors, then the read API and operator UI — the
bulk of the shipped-feature parity. Two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M6 — Analytics + detector engine

**Goal:** adapt the **ported** analytics pipeline (ingestion, run summaries, fleet rollup, version cohorts,
thresholds) and the **40 detectors** (35 rule + 5 LLM), backed by Postgres.

**Requirements / PRDs:** parity A2/A3 ([PRD 10](../../prd/10-feature-parity.md)),
[data dictionary](../../design/data-dictionary.md), [detector catalog](../../reference/detector-catalog.md),
[observability](../../design/observability.md).

**Work items (port first)**

| # | Task | Deliverable | Acceptance |
|---|---|---|---|
| 6.1 | **Port/adapt** trace-ingestion poller | ingestion | traces consumed from Jaeger/Tempo |
| 6.2 | **Port/adapt** run-summary materialization | summaries | per-run aggregates correct |
| 6.3 | **Port/adapt** fleet rollup + version-cohort summaries | rollups | cohort deltas computable |
| 6.4 | **Port/adapt** 35 rule-based detectors | detectors | all classes registered |
| 6.5 | **Port/adapt** 5 LLM detectors (feature-flagged, default off) | LLM detectors | flagged + off |
| 6.6 | Postgres schema + migrations (data dictionary) | schema | migrations apply cleanly |
| 6.7 | Configurable thresholds per detector/workload | config | thresholds honored |
| 6.8 | Corpus + detector tests | tests | fire/no-fire fixtures green |
| 6.9 | **Update design docs** | data-dictionary, detector-catalog, observability | docs match implementation |

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

---

## Milestone M7 — Read API + operator UI

**Goal:** adapt the **ported** FastAPI read API and React operator UI (Fleet Health, Run Timeline, Version
Compare, Anomaly Inbox, Agent Detail) wired to analytics.

**Requirements / PRDs:** parity A4/A5 ([PRD 10](../../prd/10-feature-parity.md)),
[API reference](../../reference/api.md), [UI accessibility](../../design/ui-accessibility.md),
[UI interaction observability](../../design/ui-interaction-observability.md).

**Work items (port first)**

| # | Task | Deliverable | Acceptance |
|---|---|---|---|
| 7.1 | **Port/adapt** FastAPI read API (`/runs`, `/runs/{id}`, `/fleet`, `/compare`, `/anomalies`) | read API | contract shapes preserved |
| 7.2 | **Port/adapt** React UI scaffold (Vite) | web app | builds + serves |
| 7.3 | **Port/adapt** Fleet Health view | view | agent cohorts + anomaly counts |
| 7.4 | **Port/adapt** Run Timeline view | view | span tree + anomaly markers |
| 7.5 | **Port/adapt** Version Compare view | view | side-by-side deltas |
| 7.6 | **Port/adapt** Anomaly Inbox view | view | triage by severity/type/agent |
| 7.7 | **Port/adapt** Agent Detail view | view | metrics, tool mix, cost trend |
| 7.8 | Wire UI ↔ API; a11y baseline | integration | keyboard + contrast pass |
| 7.9 | **Update design docs** | api, ui-accessibility, ui-interaction-observability | docs match UI/API |

**Tests required:** API contract tests (all five endpoints); UI build; view render tests; basic a11y checks.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] All five read-API endpoints return preserved shapes (parity A4)
- [ ] All five operator views render against seeded data (parity A5)
- [ ] Basic accessibility baseline met

**Design docs to update:** [api.md](../../reference/api.md), [ui-accessibility.md](../../design/ui-accessibility.md),
[ui-interaction-observability.md](../../design/ui-interaction-observability.md), [comparison.md](../../reference/comparison.md),
[CHANGELOG](../../../CHANGELOG.md).

---

Part 4 green ⇒ proceed to [Part 5 (M8–M9)](wbs-v0.1.0-part5-stack-release.md).
