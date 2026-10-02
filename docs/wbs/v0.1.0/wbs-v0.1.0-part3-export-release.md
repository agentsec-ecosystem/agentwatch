# WBS v0.1.0 — Part 3: Export, First-Run & Release (M4–M5)

**BLUF:** **Port the export + replay tooling first**, then prove the ≤15-minute first-run and ship v0.1.0 with
field-test + security evidence. Two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M4 — OTel export + replay

**Goal:** **port** the shipped OTLP export and replay/timeline concepts, then wire them so records load into
standard OTel backends unmodified (R4) and any session replays faithfully (R8).

**Requirements / PRDs:** R4, R8; [OTel mapping](../../design/otel-mapping.md),
[record-format spec](../../reference/record-format-spec.md), PRD 17 (F5/F6), DD-09.

**Work items (port first)**

| # | Task | Deliverable | Acceptance |
|---|---|---|---|
| 4.1 | **Port** OTLP export orchestrator from `agent-exec-trace` | exporter | records forwarded as OTLP |
| 4.2 | **Port** replay / run-timeline concepts | replay module | ordered timeline reconstructable |
| 4.3 | Adapt exporter to the agentwatch record + security events | mapping | `execute_tool` spans + events |
| 4.4 | Export gating on redaction self-test (DD-09) | gate | F6 test green |
| 4.5 | Export resilience — endpoint down keeps local records (F5) | retry/backoff | F5 test green |
| 4.6 | `agentwatch sessions` + `agentwatch replay <id>` | CLI paths | list + reconstruct |
| 4.7 | Replay-fidelity automated test | test | diff vs raw transcript empty (R8) |
| 4.8 | **Update design docs** | otel-mapping, runbook, record-format spec | docs match wiring |

**Tests required:** export to ≥2 backends (Phoenix + Jaeger/Tempo); export-locked-until-self-test; F5/F6;
replay fidelity diff.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] Records load unmodified in **≥2** OTel backends (R4)
- [ ] Export blocked until redaction self-test passes (DD-09); export failure loses no data (F5)
- [ ] Replay matches the raw transcript (R8, automated)

**Design docs to update:** [otel-mapping.md](../../design/otel-mapping.md),
[runbooks/export-to-otel.md](../../runbooks/export-to-otel.md), [api.md](../../reference/api.md) /
[sdk.md](../../reference/sdk.md), [record-format-spec.md](../../reference/record-format-spec.md),
[CHANGELOG](../../../CHANGELOG.md).

---

## Milestone M5 — First-run + release

**Goal:** **port the shipped CI/field-test/release tooling**, then prove a fresh machine records in ≤15
minutes and ship v0.1.0 with field-test + security evidence.

**Requirements / PRDs:** R2 (≤15 min), CUJ-1..4 ([PRD 04](../../prd/04-users-and-cujs.md)),
[PRD 07](../../prd/07-success-metrics.md) gate, [PRD 18](../../prd/18-security-compliance.md),
[PRD 13](../../prd/13-non-functional-requirements.md), [field-test plan](../../field-test/v0.1.0/field-test-plan.md),
[security audit](../../release/v0.1.0/security-audit.md).

**Work items (port first)**

| # | Task | Deliverable | Acceptance |
|---|---|---|---|
| 5.1 | **Port** CI + field-test harness + release tooling from `agent-exec-trace` | CI/scripts | pipeline runs |
| 5.2 | `agentwatch init` (install hooks, start daemon, monitor-only) | init command | first record ≤15 min |
| 5.3 | `/healthz` + `agentwatch status` (PRD 13) | health surface | `recording` only when chain intact |
| 5.4 | First-run verification (timed, clean machine) | evidence | ≤15 min, zero code changes (R2) |
| 5.5 | Field test execution | [report](../../field-test/v0.1.0/FIELD_TEST_REPORT.md) | 6 scenarios pass |
| 5.6 | Security audit | [audit](../../release/v0.1.0/security-audit.md) | 0 unresolved findings |
| 5.7 | Release artifacts (SBOM, signed, provenance) + OWASP matrix | artifacts | verifiable + published |
| 5.8 | Tag v0.1.0 (release notes + compatibility table) | tag + release | published |
| 5.9 | **Update design docs** | README, release, traceability, backlog | docs current |

**Tests required:** `/healthz` contract; all F1–F10 fault-injection green; full suite + coverage gate;
first-run timed test.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] Fresh machine → first recorded call ≤15 min, zero code changes (R2/CUJ-1)
- [ ] All P0 (R1–R8) met (PRD 07 gate); field-test + security audit + OWASP matrix published
- [ ] SBOM + signed artifacts; Scorecard grade recorded; v0.1.0 tagged

**Design docs to update:** [README](../../../README.md), [CHANGELOG](../../../CHANGELOG.md),
[release notes](../../release/v0.1.0/release-notes.md), [security audit](../../release/v0.1.0/security-audit.md),
[field-test report](../../field-test/v0.1.0/FIELD_TEST_REPORT.md), [compatibility.md](../../reference/compatibility.md),
[PRD 12](../../prd/12-traceability.md), [maintenance backlog](../../maintenance-backlog.md).

---

## v0.1.0 release gate (all milestones)

- [ ] M0–M5 exit criteria satisfied (incl. port tasks + design docs)
- [ ] R1–R8 acceptance criteria demonstrated
- [ ] Replay matches transcript; attack pack 0 leaks; fresh-machine ≤15 min
- [ ] Field test + security audit + release notes + compatibility table published
- [ ] SBOM + signed artifacts; OpenSSF Scorecard grade recorded
