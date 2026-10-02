# WBS v0.1.0 — Part 5: Stack, Demo & Full-Parity Release (M8–M9)

**BLUF:** Adapt the **ported** stack/demo/E2E, then ship v0.1.0 with full shipped-feature parity and
**delete the `agent-exec-trace` repo**. Two milestones.

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
| 8.1 | **Port/adapt** Docker Compose stack (Jaeger/Tempo, Collector, Postgres, API, analytics, web) | `docker compose up -d` | services healthy |
| 8.2 | **Port/adapt** demo agent (LangGraph `request-triage`) | `examples/demo-agent` | one-command demo |
| 8.3 | **Port/adapt** seed/replay workflow (96 runs, ~240 anomalies, 4 agents) | `make seed-e2e` | seeded data loads |
| 8.4 | **Port/adapt** E2E Playwright tests (five views) | e2e tests | E2E green |
| 8.5 | **Port/adapt** field-test harness | harness | runs the field-test plan |
| 8.6 | Wire local dev flow (`make stack-up`, `make seed-e2e`) | Makefile | documented flow works |
| 8.7 | **Update design docs** | deployment, demo-and-seed, runbooks | docs match stack |

**Tests required:** compose health; seed idempotency; Playwright E2E (5 views); field-test harness smoke.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] `docker compose up -d` healthy; `make seed-e2e` loads data (parity A6)
- [ ] E2E Playwright tests green across all five views
- [ ] Field-test harness runnable

**Design docs to update:** [deployment.md](../../deployment.md), [demo-and-seed.md](../../plans/demo-and-seed.md),
[runbooks/deploy-local-stack.md](../../runbooks/deploy-local-stack.md), [CHANGELOG](../../../CHANGELOG.md).

---

## Milestone M9 — Full-parity release + decommission

**Goal:** adapt the **ported** CI/release tooling, prove full shipped-feature parity + the security baseline,
ship **v0.1.0**, and **delete the now-redundant `agent-exec-trace` repo**.

**Requirements / PRDs:** all R1–R8, all parity A1–A6 ([PRD 10](../../prd/10-feature-parity.md)),
[PRD 07](../../prd/07-success-metrics.md) gate, [PRD 18](../../prd/18-security-compliance.md),
[PRD 12](../../prd/12-traceability.md), [security audit](../../release/v0.1.0/security-audit.md).

**Work items (port first)**

| # | Task | Deliverable | Acceptance |
|---|---|---|---|
| 9.1 | **Port/adapt** CI + release tooling | CI/scripts | pipeline runs |
| 9.2 | First-run verification (timed, clean machine) | evidence | ≤15 min, zero code changes (R2) |
| 9.3 | Field test execution | [report](../../field-test/v0.1.0/FIELD_TEST_REPORT.md) | all scenarios pass |
| 9.4 | Security audit | [audit](../../release/v0.1.0/security-audit.md) | 0 unresolved findings |
| 9.5 | SBOM + signed artifacts + provenance | artifacts | verifiable |
| 9.6 | OWASP / compliance coverage matrix (PRD 18) | matrix | published |
| 9.7 | **Parity gate** — verify A1–A6 delivered + tested | checklist | every matrix-A row green |
| 9.8 | Tag v0.1.0 (release notes + compatibility table) | tag + release | published |
| 9.9 | **Delete `agent-exec-trace`** — after the ported suite is green in CI | repo removed | 404 |
| 9.10 | **Update design docs** | README, release, traceability, backlog | docs current |

**Tests required:** full suite + coverage gate; all F1–F10 fault-injection; parity suite (A1–A6); first-run
timed test.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] **Parity A1–A6 delivered and tested** — the parity gate
- [ ] R1–R8 acceptance demonstrated; fresh-machine ≤15 min; attack pack 0 leaks
- [ ] Field test + security audit + OWASP matrix + release notes published; SBOM + signed artifacts
- [ ] v0.1.0 tagged; **`agent-exec-trace` repository deleted**

**Design docs to update:** [README](../../../README.md), [CHANGELOG](../../../CHANGELOG.md),
[release notes](../../release/v0.1.0/release-notes.md), [security audit](../../release/v0.1.0/security-audit.md),
[field-test report](../../field-test/v0.1.0/FIELD_TEST_REPORT.md), [compatibility.md](../../reference/compatibility.md),
[PRD 12](../../prd/12-traceability.md), [PRD 10](../../prd/10-feature-parity.md),
[THIRD_PARTY_NOTICES](../../../THIRD_PARTY_NOTICES.md), [maintenance backlog](../../maintenance-backlog.md).

---

## v0.1.0 release gate (all milestones)

- [ ] M0–M9 exit criteria satisfied (incl. port tasks + design docs)
- [ ] **Full shipped-feature parity A1–A6** delivered + tested
- [ ] R1–R8 acceptance demonstrated; replay matches transcript; attack pack 0 leaks; fresh-machine ≤15 min
- [ ] Field test + security audit + release notes + compatibility table published
- [ ] SBOM + signed artifacts; OpenSSF Scorecard grade recorded
- [ ] **`agent-exec-trace` deleted**
