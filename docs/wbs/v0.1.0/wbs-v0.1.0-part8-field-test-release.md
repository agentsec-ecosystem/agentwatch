# WBS v0.1.0 — Part 8: Field Tests & Release Readiness (M14–M15)

**BLUF:** Run the field tests, then execute the release-readiness checklist and ship. Mirrors hiveplane's
dedicated `field-test` and `release-readiness` parts. Two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M14 — Field Tests

**Goal:** run the field tests against the deployed build and publish the report.

**Requirements / PRDs:** [PRD 07](../../prd/07-success-metrics.md),
[PRD 12](../../prd/12-traceability.md), [field-test plan](../../field-test/v0.1.0/field-test-plan.md),
[testing & parity strategy](../../plans/testing-and-parity-strategy.md).

**Work items (port first)**

| # | Task | Deliverable | Acceptance | Issue |
|---|---|---|---|---|
| 14.1 | **Port/adapt** the field-test harness | harness | runnable | #141 |
| 14.2 | Execute field-test scenarios 1–6 (fresh install, replay, export, redaction attack, tamper, long session) | results | all scenarios pass | #142 |
| 14.3 | Collect evidence + publish `FIELD_TEST_REPORT.md` | report | published | #143 |
| 14.4 | Fix defects found; add regression tests | fixes | defects closed | #144 |
| 14.5 | Field-test CI job (nightly) | CI | scheduled + green | #145 |
| 14.T | Add/expand test cases for this milestone (unit + integration + fault-injection) | tests | all new paths covered; coverage ≥ 95% | #146 |
| 14.D | Create/update the design + reference docs for this milestone | docs | docs updated and linked from the WBS | #147 |

**Tests required:** all six field-test scenarios; regression tests for every defect found.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] All six field-test scenarios pass
- [ ] `FIELD_TEST_REPORT.md` published; defects fixed with regression tests

**Design docs to update:** [field-test plan](../../field-test/v0.1.0/field-test-plan.md),
[field-test report](../../field-test/v0.1.0/FIELD_TEST_REPORT.md), [known-limitations.md](../../reference/known-limitations.md),
[CHANGELOG](../../../CHANGELOG.md).

---

## Milestone M15 — Release Readiness

**Goal:** execute the release-readiness checklist, ship **v0.1.0**, and make `agent-exec-trace` private (retained, never deleted).

**Requirements / PRDs:** [PRD 07](../../prd/07-success-metrics.md), [PRD 09](../../prd/09-roadmap.md),
[PRD 10](../../prd/10-feature-parity.md), [PRD 18](../../prd/18-security-compliance.md),
[release notes](../../release/v0.1.0/release-notes.md), [security audit](../../release/v0.1.0/security-audit.md).

**Work items (port first)**

| # | Task | Deliverable | Acceptance | Issue |
|---|---|---|---|---|
| 15.1 | **Port/adapt** release tooling | tooling | runs | #148 |
| 15.2 | First-run verification (timed clean machine ≤15 min) | evidence | ≤15 min, zero code changes | #149 |
| 15.3 | Security audit published | [audit](../../release/v0.1.0/security-audit.md) | 0 unresolved findings | #150 |
| 15.4 | SBOM + signed artifacts + provenance | artifacts | verifiable | #151 |
| 15.5 | OWASP/compliance matrix + OpenSSF checklist | matrix | published | #152 |
| 15.6 | Versioning + backwards-compat policy validated | policy | documented + honored | #153 |
| 15.7 | Release notes + compatibility table | notes | published | #154 |
| 15.8 | Tag v0.1.0 | tag + release | published | #155 |
| 15.9 | Make `agent-exec-trace` repo private | visibility | retained + `private` | #156 |
| 15.T | Add/expand test cases for this milestone (unit + integration + fault-injection) | tests | all new paths covered; coverage ≥ 95% | #157 |
| 15.D | Create/update the design + reference docs for this milestone | docs | docs updated and linked from the WBS | #158 |

**Tests required:** full suite + coverage gate; parity suite (A1–A6); first-run timed test.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] Full PRD coverage + shipped-feature parity A1–A6 delivered and tested
- [ ] First-run ≤15 min; security audit + OWASP matrix + release notes published; SBOM + signed artifacts
- [ ] v0.1.0 tagged; **`agent-exec-trace` repository retained and made private**

**Design docs to update:** [README](../../../README.md), [CHANGELOG](../../../CHANGELOG.md),
[release notes](../../release/v0.1.0/release-notes.md), [security audit](../../release/v0.1.0/security-audit.md),
[compatibility.md](../../reference/compatibility.md), [versioning-policy.md](../../reference/versioning-policy.md),
[backwards-compatibility-policy.md](../../reference/backwards-compatibility-policy.md),
[PRD 12](../../prd/12-traceability.md), [THIRD_PARTY_NOTICES](../../../THIRD_PARTY_NOTICES.md),
[maintenance backlog](../../maintenance-backlog.md).

---

## v0.1.0 release gate (all milestones)

- [ ] M0–M15 exit criteria satisfied (incl. port tasks + design docs)
- [ ] Full PRD coverage + shipped-feature parity A1–A6 delivered + tested
- [ ] R1–R13 acceptance demonstrated; replay matches transcript; attack pack 0 leaks; fresh-machine ≤15 min
- [ ] NFRs met; F1–F10 fail-closed
- [ ] Field tests pass; security audit + OWASP matrix + release notes published
- [ ] SBOM + signed artifacts; OpenSSF Scorecard grade recorded
- [ ] **`agent-exec-trace` retained and made private (not deleted)**
