# WBS v0.1.0 — Part 5: Stack, Demo, Inventory & Retention (M8–M9)

**BLUF:** Adapt the **ported** stack/demo/E2E, then add the new capabilities for PRD R9 (inventory) and R11
(retention). Two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M8 — Local stack + demo/seed + E2E

**Goal:** adapt the **ported** Docker Compose stack, demo agent, seed/replay workflow, and E2E (Playwright) +
field-test harness, so the whole system runs locally and is demoable.

**Requirements / PRDs:** parity A6 ([PRD 10](../../prd/10-feature-parity.md)),
[deployment](../../deployment.md), [demo & seed](../../plans/demo-and-seed.md),
[field-test plan](../../field-test/v0.1.0/field-test-plan.md), [testing & parity strategy](../../plans/testing-and-parity-strategy.md).

**Work items (port first)**

| # | Task | Deliverable | Acceptance |
|---|---|---|---|
| 8.1 | **Port/adapt** Docker Compose stack | `docker compose up -d` | services healthy |
| 8.2 | **Port/adapt** demo agent (LangGraph `request-triage`) | `examples/demo-agent` | one-command demo |
| 8.3 | **Port/adapt** seed/replay workflow (96 runs, ~240 anomalies, 4 agents) | `make seed-e2e` | seeded data loads |
| 8.4 | **Port/adapt** E2E Playwright tests (five views) | e2e tests | E2E green |
| 8.5 | **Port/adapt** field-test harness | harness | runs the plan |
| 8.6 | Wire local dev flow (`make stack-up`, `make seed-e2e`) | Makefile | documented flow works |
| 8.7 | **Update design docs** | deployment, demo-and-seed, runbooks | docs match stack |

**Tests required:** compose health; seed idempotency; Playwright E2E (5 views); field-test harness smoke.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] `docker compose up -d` healthy; `make seed-e2e` loads data (parity A6)
- [ ] E2E Playwright tests green across all five views

**Design docs to update:** [deployment.md](../../deployment.md), [demo-and-seed.md](../../plans/demo-and-seed.md),
[runbooks/deploy-local-stack.md](../../runbooks/deploy-local-stack.md), [CHANGELOG](../../../CHANGELOG.md).

---

## Milestone M9 — Inventory + retention (R9, R11)

**Goal:** add the **shadow-agent / MCP-server inventory** (R9) and harden **retention controls +
tamper-evident hash-chaining** (R11) — net-new capabilities beyond the port.

**Requirements / PRDs:** R9, R11 ([PRD 05](../../prd/05-features.md)),
[data model lifecycle](../../prd/15-data-model.md), [storage design](../../design/storage-design.md),
[PRD 16](../../prd/16-configuration.md).

**Work items (port first)**

| # | Task | Deliverable | Acceptance |
|---|---|---|---|
| 9.1 | **Port/adapt** inventory data from the ported record store | inventory source | reads recorded agents/servers |
| 9.2 | Shadow-agent inventory (what agents exist locally) | `inventory` module | lists local agents |
| 9.3 | MCP-server inventory | inventory | lists local MCP servers |
| 9.4 | `agentwatch inventory` CLI | CLI path | prints inventory |
| 9.5 | Retention controls hardening (`retention_days`, `max_size_mb`) | retention | enforced + tombstoned |
| 9.6 | Hash-chaining retention / tombstoning (no silent gap) | chain | verify-store clean after purge |
| 9.7 | **Update design docs** | storage, data model, cli-reference | docs match behavior |

**Tests required:** inventory discovery; retention purge + tombstone; chain integrity after purge.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] Inventory lists local agents + MCP servers (R9)
- [ ] Retention enforced; purge tombstoned; `verify-store` clean (R11)

**Design docs to update:** [storage-design.md](../../design/storage-design.md), [PRD 15](../../prd/15-data-model.md),
[cli-reference.md](../../reference/cli-reference.md), [CHANGELOG](../../../CHANGELOG.md).

---

Part 5 green ⇒ proceed to [Part 6 (M10–M11)](wbs-v0.1.0-part6-expansion.md).
