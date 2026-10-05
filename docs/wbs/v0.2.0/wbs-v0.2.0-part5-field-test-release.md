# WBS v0.2.0 — Part 5: Field Tests & Release Readiness (M29–M30)

**BLUF:** Prepare the test environment, run the field tests, publish the report, then execute the full
release-readiness checklist and ship **v0.2.0** — security scans, all docs, merge to main, tag, publish to
PyPI/npm, and post-release verification. **Always the last two** (M29, M30), after the implementation milestones
M25–M28.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **WBS updated** · **issues updated** · **all relevant documents updated as the
> milestone is closed out** · **code committed and pushed** · design docs updated.

---

## Milestone M29 — Field Tests (PRD 40, 43, 47)

**Status:** ⏳ not started

**Goal:** Prepare a reproducible test environment, add the v0.2.0 cases, run the field tests against the deployed
build, and publish the report (with observations, learnings, and takeaways) — exercising the new surfaces and
CUJ-15–20.

**Requirements / PRDs:** [PRD 40](../../prd/40-v0.2.0-program.md) §5,
[PRD 43](../../prd/43-detector-credibility-and-evaluation.md), [PRD 47](../../prd/47-cross-harness-testkit.md),
[PRD 04 CUJ-15–20](../../prd/04-users-and-cujs.md), field-test plan (`docs/field-test/v0.2.0/`).

**Work items**

| # | Task | Deliverable | Dependencies | Acceptance | Issue |
|---|---|---|---|---|---|
| 29.1 | Prepare the Docker/compose environment for field testing | environment | M25–M28 | Stack builds and comes up healthy; seed loads; reset/teardown work | #408 |
| 29.2 | Update the field-test scripts/drivers | scripts | 29.1 | Each script runs end to end against the composed stack | #409 |
| 29.3 | Add new v0.2.0 field-test cases | test cases | 29.2 | Cases exist for every v0.2.0 surface and are discoverable | #410 |
| 29.4 | Port/adapt the v0.2.0 field-test harness | harness | 29.3 | Runnable harness drives compose + seed + E2E, extended for v0.2.0 | #389 |
| 29.5 | Execute the v0.2.0 field-test scenarios | results | 29.4 | All scenarios pass, 0 skips (install · AAT · harness · MCP · stream · trace · comply · detectors · hostile) | #390 |
| 29.6 | Collect evidence + publish the field-test report | report | 29.5 | Published with observations, learnings, takeaways + CUJ-15–20 verification | #391 |
| 29.7 | Fix field-test defects; add regression tests | fixes | 29.5 | Every defect closed with a regression test | #392 |
| 29.8 | Field-test CI job (nightly) | CI | 29.4 | Scheduled + green, or recorded not-planned with a reason | #393 |
| 29.9 | Cross-harness test-kit validation (XHT) | evidence | 25.XHT-1, 26.XHT-2, 27.XHT-3 | Corpus replay + live OpenCode soak green; fidelity tiers verified | #394 |
| 29.10 | Detector reproduction on a second corpus (CUJ-19) | evidence | 26.DET-3, 26.COR-1 | Local numbers match published numbers within stated bounds | #395 |
| 29.T | Add/expand test cases for this milestone | tests | M29 feature items | All new paths covered; coverage ≥ 95% | #383 |
| 29.D | Create/update the design + reference docs for this milestone | docs | M29 feature items | Docs updated and linked from the WBS | #384 |
| 29.R | Code review & risk sign-off for this milestone | review | M29 + 29.T + 29.D | Review recorded; no unresolved findings | #385 |

> **Umbrella:** FLD-1 (#370) — the field-test capability from PRD 46; the milestone work items above are its
> decomposition.

**Field-test report — required sections:** executive summary; environment/setup; scenario matrix; per-suite
results; **observations**; **learnings**; **takeaways**; defects + regressions; coverage/gaps; CUJ-15–20
verification; evidence paths.

**Field-test suites**

| Suite | Proves | Evidence path |
|---|---|---|
| Fresh install | CUJ-1 ≤15 min, zero code changes | `field-test/v0.2.0/results/install/` |
| AAT | export validates with an external consumer (CUJ-15) | `field-test/v0.2.0/results/aat/` |
| Harness fidelity | Cursor/Gemini/Codex fidelity vs golden corpus | `field-test/v0.2.0/results/harness/` |
| MCP full surface | resources/prompts/elicitation/tasks across 3 revisions | `field-test/v0.2.0/results/mcp/` |
| Streaming | p99 ≤1 s; drop-consumer reconciliation; soak | `field-test/v0.2.0/results/stream/` |
| Identity/trace | cross-agent/host attribution (CUJ-16) | `field-test/v0.2.0/results/trace/` |
| Compliance | offline report, every row regenerable (CUJ-18) | `field-test/v0.2.0/results/comply/` |
| Detectors | published numbers reproduced (CUJ-19) | `field-test/v0.2.0/results/det/` |
| Hostile data | weaponized input contained (R5/ADR-0024) | `field-test/v0.2.0/results/hostile/` |

**Tests required:** all field-test scenarios; regression tests for every defect; CUJ-15–20 end to end.

**Exit criteria**

- [ ] All field-test tests pass · coverage ≥ 95% · lint strict clean · WBS + issues updated · **all relevant
      documents updated** · pushed
- [ ] All v0.2.0 scenarios pass; report published with observations/learnings/takeaways; defects fixed with
      regressions; CUJ-15–20 verified end to end

**Documents to update at close-out:** `field-test/v0.2.0/` (env + plan + report + results),
[PRD 40](../../prd/40-v0.2.0-program.md), [PRD 43](../../prd/43-detector-credibility-and-evaluation.md),
[PRD 47](../../prd/47-cross-harness-testkit.md), [guides/user-guide.md](../../guides/user-guide.md),
[reference/known-limitations.md](../../reference/known-limitations.md), [CHANGELOG](../../../CHANGELOG.md).

---

## Milestone M30 — Release Readiness (PRD 07, 09, 40)

**Status:** ⏳ not started

**Goal:** Execute the full release-readiness checklist and ship **v0.2.0**: scan, audit, sign, document, merge to
main, tag, publish, and verify — plus the naming outcome.

**Requirements / PRDs:** [PRD 40](../../prd/40-v0.2.0-program.md) §5,
[PRD 07](../../prd/07-success-metrics.md), [PRD 09](../../prd/09-roadmap.md),
[PRD 18](../../prd/18-security-compliance.md), [PRD 12](../../prd/12-traceability.md),
[gtm.md](../../gtm.md), release notes/audit under `docs/release/v0.2.0/`.

> **Canonical release:** M30 is where the branch merges to **main**, the tag is cut, and the artifacts are
> published. Do not tag before M30.

**Work items**

| # | Task | Deliverable | Dependencies | Acceptance | Issue |
|---|---|---|---|---|---|
| 30.1 | Port/adapt the release tooling | tooling | M13/Q13 | Build + SBOM + checksums + verify-release run; dry-run green | #396 |
| 30.2 | Release checklist + go/no-go review | checklist | 30.1 | Signed-off checklist covering every PRD 40 §5 gate | #411 |
| 30.3 | Version bump + single-version consistency | version | 30.1 | One version across SDK/CLI/CHANGELOG, enforced by test | #412 |
| 30.4 | Security scans (secrets + dependencies + egress) | scan report | 30.1 | `make security-scan` clean on the release commit | #413 |
| 30.5 | Security audit published + findings remediated | audit | 30.4 | `security-audit.md` published, 0 unresolved findings | #398 |
| 30.6 | Dependency + license review + THIRD_PARTY_NOTICES | review | 30.4 | No new runtime dep without a decision; notices current | #414 |
| 30.7 | SBOM + checksums + Sigstore signing + build provenance | signed artifacts | 30.1 | All verify | #399 |
| 30.8 | Full test suite + coverage gate on the release commit | test run | 30.1 | Whole-repo CI green at HEAD | #415 |
| 30.9 | First-run verification (timed clean machine ≤15 min) | first-run evidence | 29.4 | ≤15 min, zero code changes, recorded | #397 |
| 30.10 | Update release notes | release notes | 30.8 | `release-notes.md` published | #402 |
| 30.11 | Update CHANGELOG | changelog | 30.8 | Dated `[0.2.0]` section + compare links | #416 |
| 30.12 | Update README + ROADMAP + docs index | top-level docs | 30.8 | Reflect the release | #417 |
| 30.13 | Update reference docs (compatibility, known-limitations, versioning, claims ledger) | reference docs | 30.8 | Regenerated + reconciled | #401 |
| 30.14 | Update PRD statuses (40–48 → shipped) + migration notes | PRDs + migration | 30.8 | Shipped status; upgrade notes published | #418 |
| 30.15 | Compliance matrix + OpenSSF checklist + Scorecard grade | compliance | 30.8 | Published; grade recorded | #400 |
| 30.16 | Execute the ADR-0026 naming outcome | naming action | ADR-0026 | Decision implemented; install guard ships | #404 |
| 30.17 | Known-limitations shrink verification | evidence | M26–M28 | G1/G2/G4/G7/G8 leave with proving tests | #405 |
| 30.18 | AAT external third-party consumer verification | evidence | 29.5 | Independent consumer validates released AAT | #406 |
| 30.19 | Detector numbers published + claims ledger green | published numbers | 26.DET-3 | Numbers + method published; ledger passes | #407 |
| 30.20 | Cut the release branch + merge feat-v0.2.0 → main | merge | 30.2–30.19 | Reviewed PR merges to main; main is the release commit | #419 |
| 30.21 | Tag v0.2.0 + GitHub release | tag | 30.20 | Tagged on main; GitHub release with notes/SBOM/checksums/provenance | #403 |
| 30.22 | Publish to PyPI + npm (trusted publishing) | published artifacts | 30.21 | Installs/launches from the published registry | #420 |
| 30.23 | Post-release install verification (fresh install) | evidence | 30.22 | Clean-machine install records + verifies | #421 |
| 30.24 | Publish release content (GTM: stories + articles) | content | 30.21 | Three stories + article set published | #422 |
| 30.25 | Backfill WBS issue numbers + reconcile docs and GitHub | docs reconciliation | 30.21 | Every WBS row has its real issue number | #423 |
| 30.26 | Traceability (PRD 12) + glossary updates for v0.2.0 | docs | M25–M29 | Traceability map + glossary updated | #437 |
| 30.T | Add/expand test cases for this milestone | tests | release items | All new paths covered; coverage ≥ 95% | #386 |
| 30.D | Create/update the design + reference docs for this milestone | docs | release items | Docs updated and linked from the WBS | #387 |
| 30.R | Code review & risk sign-off for this milestone | review | 30.T + 30.D | Final sign-off recorded | #388 |

**Validation evidence (30.1–30.19)**

| Item | Evidence |
|---|---|
| 30.4 Security scan | `make security-scan` + `docs/release/v0.2.0/secret-scan-report.md` |
| 30.5 Audit | `docs/release/v0.2.0/security-audit.md` |
| 30.7 Artifacts | `docs/release/v0.2.0/release-evidence.md`; `make release-dry-run` |
| 30.9 First run | `docs/release/v0.2.0/first-run-evidence.md` |
| 30.15 Compliance | `docs/release/v0.2.0/compliance-matrix.md`; `reference/open-source-checklist.md` |
| 30.13 Reference | `reference/compatibility.md`; `known-limitations.md`; `docs/release/claims-ledger.json` |

**Tests required:** full suite + coverage gate; release-gate suite; first-run timed test; forward-compat matrix;
naming install-guard test.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · WBS + issues updated · **all relevant documents
      updated** · pushed
- [ ] The eight [PRD 40](../../prd/40-v0.2.0-program.md) §5 release-gate criteria all pass at the release commit
- [ ] Security scan + audit + SBOM/signing clean; all docs updated; merged to main; tagged; published; post-install
      verified; naming outcome executed

**Documents to update at close-out:** [README](../../../README.md), [CHANGELOG](../../../CHANGELOG.md),
[ROADMAP.md](../../../ROADMAP.md), [docs/README.md](../../README.md), `docs/release/v0.2.0/`,
[reference/compatibility.md](../../reference/compatibility.md),
[reference/versioning-policy.md](../../reference/versioning-policy.md),
[reference/backwards-compatibility-policy.md](../../reference/backwards-compatibility-policy.md),
[reference/known-limitations.md](../../reference/known-limitations.md),
[reference/v0.2.0-research-sources.md](../../reference/v0.2.0-research-sources.md), [gtm.md](../../gtm.md),
[PRD 12](../../prd/12-traceability.md), [glossary](../../glossary.md),
[THIRD_PARTY_NOTICES](../../../THIRD_PARTY_NOTICES.md), [maintenance-backlog.md](../../maintenance-backlog.md),
all PRDs 40–48.

---

## v0.2.0 release gate (all milestones)

- [ ] M25–M30 exit criteria satisfied (incl. design docs + all relevant documents updated)
- [ ] PRD 40–48 scope delivered; cut-line items shipped or explicitly phased with re-pointed issues
- [ ] AAT third-party round-trip verified externally (CUJ-15); no "modeled" Tier-1 rows
- [ ] Streaming p99 ≤1 s (CUJ-17); cross-agent/host attribution (CUJ-16); compliance report offline (CUJ-18);
      detector numbers reproduced (CUJ-19); A2A delegation provable (CUJ-20)
- [ ] `known-limitations.md` shrink verified (G1/G2/G4/G7/G8 removed with proving tests)
- [ ] Field tests pass; security scan + audit + SBOM/signing published; compliance matrix + Scorecard recorded
- [ ] Merged to main; **`v0.2.0` tagged and published (PyPI + npm)**; post-release install verified
- [ ] ADR-0026 naming outcome executed; claims ledger green; WBS issue numbers backfilled
