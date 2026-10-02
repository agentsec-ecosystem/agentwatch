# WBS v0.1.0 — Part 7: NFRs, Resilience & Release (M12–M13)

**BLUF:** Implement the cross-cutting non-functional requirements and error handling (PRD 13, 17), then ship
v0.1.0 with compliance evidence, full PRD coverage, and **predecessor retention** (the old repo is made
private, never deleted). Two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M12 — NFRs + resilience + error handling

**Goal:** implement and verify **NFR-1..NFR-12** ([PRD 13](../../prd/13-non-functional-requirements.md)) and
**F1–F10** ([PRD 17](../../prd/17-error-handling.md)): performance, sizing, self-observability, fail-closed
behavior, accessibility, and i18n.

**Requirements / PRDs:** [PRD 13](../../prd/13-non-functional-requirements.md),
[PRD 17](../../prd/17-error-handling.md), [PRD 06](../../prd/06-security-baseline.md),
[performance budget](../../design/performance-budget.md), [sizing](../../design/sizing.md),
[ui-accessibility](../../design/ui-accessibility.md), [i18n](../../reference/i18n.md),
[threat-test traceability](../../design/threat-test-traceability.md).

**Work items (port first)**

| # | Task | Deliverable | Acceptance | Issue | Issue |
|---|---|---|---|---|---|
| 12.1 | **Port/adapt** perf measurement hooks | perf harness | p99 step latency measured | #93 |
| 12.2 | Perf budget met (NFR-1 ≤5 ms/step; NFR-2..4) | perf tests | p99 within budget | #94 |
| 12.3 | Sizing verified (NFR-3, NFR-5..7) | sizing doc/tests | within caps | #95 |
| 12.4 | `/healthz` + `agentwatch status` (NFR-12 self-observability) | health surface | states correct | #96 |
| 12.5 | Fault-injection suite **F1–F10** (PRD 17) | fault tests | all fail-closed/surfaced | #97 |
| 12.6 | Fail-closed verification (NFR-8) | tests | no silent stop | #98 |
| 12.7 | Accessibility pass (NFR-10) | a11y checks | keyboard + contrast | #99 |
| 12.8 | i18n baseline (UTC, English-first) | formatting | locale-independent records | #100 |
| 12.9 | **Update design docs** | perf, sizing, a11y, i18n, error-handling | docs match behavior | #101 |
| 12.T | Add/expand test cases for this milestone (unit + integration + fault-injection) | tests | all new paths covered; coverage ≥ 95% | #137 |
| 12.D | Create/update the design + reference docs for this milestone | docs | docs updated and linked from the WBS | #138 |

**Tests required:** perf (p99 ≤5 ms); F1–F10; health contract; a11y; i18n/UTC.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] NFR-1..NFR-12 met (perf, sizing, self-observability, a11y, i18n)
- [ ] **F1–F10 fault-injection green** — every failure fails closed and is surfaced
- [ ] `/healthz` reports `recording` only when the chain is intact

**Design docs to update:** [performance-budget.md](../../design/performance-budget.md), [sizing.md](../../design/sizing.md),
[ui-accessibility.md](../../design/ui-accessibility.md), [i18n.md](../../reference/i18n.md),
[PRD 13](../../prd/13-non-functional-requirements.md), [PRD 17](../../prd/17-error-handling.md),
[resource-cost.md](../../reference/resource-cost.md), [CHANGELOG](../../../CHANGELOG.md).

---

## Milestone M13 — Compliance + full-parity release + predecessor retention

**Goal:** port the CI/release tooling, prove **full PRD coverage + shipped-feature parity**, ship **v0.1.0**,
and **make the `agent-exec-trace` repo private** (retained, never deleted).

**Requirements / PRDs:** all R1–R13, parity A1–A6 ([PRD 10](../../prd/10-feature-parity.md)),
[PRD 18](../../prd/18-security-compliance.md), [PRD 07](../../prd/07-success-metrics.md),
[PRD 09](../../prd/09-roadmap.md), [PRD 12](../../prd/12-traceability.md),
[security audit](../../release/v0.1.0/security-audit.md).

**Work items (port first)**

| # | Task | Deliverable | Acceptance | Issue | Issue |
|---|---|---|---|---|---|
| 13.1 | **Port/adapt** CI + release tooling | CI/scripts | pipeline runs | #102 |
| 13.2 | First-run verification (timed, clean machine) | evidence | ≤15 min, zero code changes (R2) | #103 |
| 13.3 | Field test execution | [report](../../field-test/v0.1.0/FIELD_TEST_REPORT.md) | all scenarios pass | #104 |
| 13.4 | Security audit | [audit](../../release/v0.1.0/security-audit.md) | 0 unresolved findings | #105 |
| 13.5 | SBOM + signed artifacts + provenance | artifacts | verifiable | #106 |
| 13.6 | OWASP/compliance matrix + OpenSSF checklist (PRD 18) | matrix | published | #107 |
| 13.7 | **Parity gate + full PRD-coverage check** | checklist | all PRD items delivered + tested | #108 |
| 13.8 | Versioning/backwards-compat policy validated | policy | documented + honored | #109 |
| 13.9 | Tag v0.1.0 (release notes + compatibility table) | tag + release | published | #110 |
| 13.10 | **Make `agent-exec-trace` private** | repo visibility | retained + `private` | #111 |
| 13.11 | **Update design docs** | README, release, traceability, backlog | docs current | #112 |
| 13.T | Add/expand test cases for this milestone (unit + integration + fault-injection) | tests | all new paths covered; coverage ≥ 95% | #139 |
| 13.D | Create/update the design + reference docs for this milestone | docs | docs updated and linked from the WBS | #140 |

**Tests required:** full suite + coverage gate; parity suite (A1–A6); first-run timed; PRD-coverage check.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] **Full PRD coverage + shipped-feature parity A1–A6** delivered and tested
- [ ] R1–R13 acceptance demonstrated; fresh-machine ≤15 min; attack pack 0 leaks
- [ ] Field test + security audit + OWASP matrix + release notes published; SBOM + signed artifacts
- [ ] v0.1.0 tagged; **`agent-exec-trace` repository retained and made private**

**Design docs to update:** [README](../../../README.md), [CHANGELOG](../../../CHANGELOG.md),
[release notes](../../release/v0.1.0/release-notes.md), [security audit](../../release/v0.1.0/security-audit.md),
[field-test report](../../field-test/v0.1.0/FIELD_TEST_REPORT.md), [compatibility.md](../../reference/compatibility.md),
[versioning-policy.md](../../reference/versioning-policy.md), [backwards-compatibility-policy.md](../../reference/backwards-compatibility-policy.md),
[PRD 12](../../prd/12-traceability.md), [PRD 10](../../prd/10-feature-parity.md),
[THIRD_PARTY_NOTICES](../../../THIRD_PARTY_NOTICES.md), [maintenance backlog](../../maintenance-backlog.md).

---

## v0.1.0 release gate (all milestones)

- [ ] M0–M13 exit criteria satisfied (incl. port tasks + design docs)
- [ ] **Full PRD coverage** + shipped-feature parity A1–A6 delivered + tested
- [ ] R1–R13 acceptance demonstrated; replay matches transcript; attack pack 0 leaks; fresh-machine ≤15 min
- [ ] NFRs met; F1–F10 fail-closed
- [ ] Field test + security audit + OWASP matrix + release notes published
- [ ] SBOM + signed artifacts; OpenSSF Scorecard grade recorded
- [ ] **`agent-exec-trace` retained and made private (not deleted)**
