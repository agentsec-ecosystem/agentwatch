# WBS v0.2.0 — Part 7: Field Tests & Release Readiness (M31–M32)

**BLUF:** Prepare the test environment, run the field tests, publish the report, then execute the full
release-readiness checklist and ship **v0.2.0** — security scans, all docs, merge to main, tag, publish to
PyPI/npm, and post-release verification. **Always the last two milestones** (M31, M32), after the implementation
milestones M25–M30. *(Renumbered from M29/M30 when the expanded milestones M29–M30 were inserted; see the
[index](wbs-v0.2.0-index.md). Their scope is unchanged, extended with the v0.2.0-expanded cases.)*

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **WBS updated** · **issues updated** · **all relevant documents updated as the
> milestone is closed out** · **code committed and pushed** · design docs updated.

---

## Milestone M31 — Field Tests (PRD 40, 43, 47)

**Status:** ⏳ not started

**Goal:** Prepare a reproducible test environment, add the v0.2.0 + expanded cases, run the field tests against the
deployed build, and publish the report (with observations, learnings, and takeaways) — exercising the new surfaces and
CUJ-15–34.

**Requirements / PRDs:** [PRD 40](../../prd/40-v0.2.0-program.md) §5,
[PRD 43](../../prd/43-detector-credibility-and-evaluation.md), [PRD 47](../../prd/47-cross-harness-testkit.md),
[PRD 04 CUJ-15–34](../../prd/04-users-and-cujs.md), PRDs 49–59, field-test plan (`docs/field-test/v0.2.0/`).

**Work items**

| # | Task | Deliverable | Dependencies | Acceptance | Issue |
|---|---|---|---|---|---|
| 31.1 | Prepare the Docker/compose environment for field testing | environment | M25–M30 | Stack builds and comes up healthy; seed loads; reset/teardown work | #408 |
| 31.2 | Update the field-test scripts/drivers | scripts | 31.1 | Each script runs end to end against the composed stack | #409 |
| 31.3 | Add new v0.2.0 field-test cases | test cases | 31.2 | Cases exist for every v0.2.0 surface and are discoverable | #410 |
| 31.4 | Port/adapt the v0.2.0 field-test harness | harness | 31.3 | Runnable harness drives compose + seed + E2E, extended for v0.2.0 | #389 |
| 31.5 | Execute the v0.2.0 field-test scenarios | results | 31.4 | All scenarios pass, 0 skips (install · AAT · harness · MCP · stream · trace · comply · detectors · hostile) | #390 |
| 31.6 | Collect evidence + publish the field-test report | report | 31.5 | Published with observations, learnings, takeaways + CUJ verification | #391 |
| 31.7 | Fix field-test defects; add regression tests | fixes | 31.5 | Every defect closed with a regression test | #392 |
| 31.8 | Field-test CI job (nightly) | CI | 31.4 | Scheduled + green, or recorded not-planned with a reason | #393 |
| 31.9 | Cross-harness test-kit validation (XHT) | evidence | 25.XHT-1, 26.XHT-2, 27.XHT-3 | Corpus replay + live OpenCode soak green; fidelity tiers verified | #394 |
| 31.10 | Detector reproduction on a second corpus (CUJ-19) | evidence | 26.DET-3, 26.COR-1 | Local numbers match published numbers within stated bounds | #395 |
| 31.11 | Expanded field cases: APV/CCO/DEP | results | 29.APV-1..3, 29.CCO-1, 29.DEP-1..3 | FT-APV-1/2, FT-CCO-1, FT-DEP-1/2/3 pass | #488 |
| 31.12 | Expanded field cases: CAP/MEM/PRV | results | 30.CAP-1/2, 30.MEM-1, 30.PRV-1 | FT-CAP-1, FT-MEM-1, FT-PRV-1 pass | #489 |
| 31.13 | Expanded field cases: LUI/AGI/POL/ASI/FWK | results | 30.LUI-1, 30.AGI-1, 30.POL-1, 29.ASI-1, 29.FWK-1 | FT-LUI-1, FT-AGI-1, FT-POL-1, FT-ASI-1, FT-FWK-1 pass | #490 |
| 31.14 | Expanded field cases: ACC/HLD/ENV/VFY/IR/RUN | results | 29.ACC-1, 29.HLD-1, 30.ENV-1, 30.VFY-1, 30.IR-1, 30.RUN-1 | FT-ACC-1, FT-HLD-1, FT-ENV-1, FT-VFY-1, FT-IR-1, FT-RUN-1 pass | #491 |
| 31.T | Add/expand test cases for this milestone | tests | M31 feature items | All new paths covered; coverage ≥ 95% | #383 |
| 31.D | Create/update the design + reference docs for this milestone | docs | M31 feature items | Docs updated and linked from the WBS | #384 |
| 31.R | Code review & risk sign-off for this milestone | review | M31 + 31.T + 31.D | Review recorded; no unresolved findings | #385 |

> **Umbrella:** FLD-1 (#370) — the field-test capability from PRD 46; the milestone work items above are its
> decomposition. Issue numbers in the `TBD` rows are assigned when the tracking issues are created and moved onto
> the M31 GitHub milestone.

**Field-test report — required sections:** executive summary; environment/setup; scenario matrix; per-suite
results; **observations**; **learnings**; **takeaways**; defects + regressions; coverage/gaps; CUJ-15–34
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
| **Authorization/oversight** | classifier/bypass never `user` (CUJ-21) | `field-test/v0.2.0/results/apv/` |
| **Deployability** | managed-policy `doctor` + attestation (CUJ-25) | `field-test/v0.2.0/results/dep/` |
| **Capability supply chain** | Plugin4Shell-shape drift (CUJ-23) | `field-test/v0.2.0/results/cap/` |
| **Console** | zero-Docker ≤60 s + UI=CLI parity (CUJ-24) | `field-test/v0.2.0/results/lui/` |
| **Provenance** | commit→session; Agent Trace validates (CUJ-22) | `field-test/v0.2.0/results/prv/` |
| **Agent interfaces / policy** | read-only MCP safety; what-if (CUJ-26/27) | `field-test/v0.2.0/results/agi-pol/` |
| **Governance / hold / verifier** | role denials; holds; browser verify (CUJ-31/32/8 ext.) | `field-test/v0.2.0/results/gov/` |

**Tests required:** all field-test scenarios; regression tests for every defect; CUJ-15–34 end to end.

**Exit criteria**

- [ ] All field-test tests pass · coverage ≥ 95% · lint strict clean · WBS + issues updated · **all relevant
      documents updated** · pushed
- [ ] All v0.2.0 + expanded scenarios pass; report published with observations/learnings/takeaways; defects fixed with
      regressions; CUJ-15–34 verified end to end

**Documents to update at close-out:** `field-test/v0.2.0/` (env + plan + report + results),
[PRD 40](../../prd/40-v0.2.0-program.md), [PRD 43](../../prd/43-detector-credibility-and-evaluation.md),
[PRD 47](../../prd/47-cross-harness-testkit.md), PRDs 49–59, [guides/user-guide.md](../../guides/user-guide.md),
[reference/known-limitations.md](../../reference/known-limitations.md), [CHANGELOG](../../../CHANGELOG.md).

---

## Milestone M32 — Release Readiness (PRD 07, 09, 40)

**Status:** ⏳ not started

**Goal:** Execute the full release-readiness checklist and ship **v0.2.0**: scan, audit, sign, document, merge to
main, tag, publish, and verify — plus the naming outcome.

**Requirements / PRDs:** [PRD 40](../../prd/40-v0.2.0-program.md) §5,
[PRD 07](../../prd/07-success-metrics.md), [PRD 09](../../prd/09-roadmap.md),
[PRD 18](../../prd/18-security-compliance.md), [PRD 12](../../prd/12-traceability.md),
[gtm.md](../../gtm.md), release notes/audit under `docs/release/v0.2.0/`.

> **Canonical release:** M32 is where the branch merges to **main**, the tag is cut, and the artifacts are
> published. Do not tag before M32.

**Work items**

| # | Task | Deliverable | Dependencies | Acceptance | Issue |
|---|---|---|---|---|---|
| 32.1 | Port/adapt the release tooling | tooling | M13/Q13 | Build + SBOM + checksums + verify-release run; dry-run green | #396 |
| 32.2 | Release checklist + go/no-go review | checklist | 32.1 | Signed-off checklist covering every PRD 40 §5 gate | #411 |
| 32.3 | Version bump + single-version consistency | version | 32.1 | One version across SDK/CLI/CHANGELOG, enforced by test | #412 |
| 32.4 | Security scans (secrets + dependencies + egress) | scan report | 32.1 | `make security-scan` clean on the release commit | #413 |
| 32.5 | Security audit published + findings remediated | audit | 32.4 | `security-audit.md` published, 0 unresolved findings | #398 |
| 32.6 | Dependency + license review + THIRD_PARTY_NOTICES | review | 32.4 | No new runtime dep without a decision; notices current | #414 |
| 32.7 | SBOM + checksums + Sigstore signing + build provenance | signed artifacts | 32.1 | All verify | #399 |
| 32.8 | Full test suite + coverage gate on the release commit | test run | 32.1 | Whole-repo CI green at HEAD | #415 |
| 32.9 | First-run verification (timed clean machine ≤15 min) | first-run evidence | 31.4 | ≤15 min, zero code changes, recorded | #397 |
| 32.10 | Update release notes | release notes | 32.8 | `release-notes.md` published | #402 |
| 32.11 | Update CHANGELOG | changelog | 32.8 | Dated `[0.2.0]` section + compare links | #416 |
| 32.12 | Update README + ROADMAP + docs index | top-level docs | 32.8 | Reflect the release | #417 |
| 32.13 | Update reference docs (compatibility, known-limitations, versioning, claims ledger) | reference docs | 32.8 | Regenerated + reconciled | #401 |
| 32.14 | Update PRD statuses (40–59 → shipped) + migration notes | PRDs + migration | 32.8 | Shipped status; upgrade notes published | #418 |
| 32.15 | Compliance matrix + OpenSSF checklist + Scorecard grade | compliance | 32.8 | Published; grade recorded | #400 |
| 32.16 | Execute the ADR-0026 naming outcome | naming action | ADR-0026 | Decision implemented; install guard ships | #404 |
| 32.17 | Known-limitations shrink verification | evidence | M26–M30 | G1/G2/G4/G7/G8 leave with proving tests | #405 |
| 32.18 | AAT external third-party consumer verification | evidence | 31.5 | Independent consumer validates released AAT | #406 |
| 32.19 | Detector numbers published + claims ledger green | published numbers | 26.DET-3 | Numbers + method published; ledger passes | #407 |
| 32.20 | Cut the release branch + merge feat-v0.2.0 → main | merge | 32.2–32.19 | Reviewed PR merges to main; main is the release commit | #419 |
| 32.21 | Tag v0.2.0 + GitHub release | tag | 32.20 | Tagged on main; GitHub release with notes/SBOM/checksums/provenance | #403 |
| 32.22 | Publish to PyPI + npm (trusted publishing) | published artifacts | 32.21 | Installs/launches from the published registry | #420 |
| 32.23 | Post-release install verification (fresh install) | evidence | 32.22 | Clean-machine install records + verifies | #421 |
| 32.24 | Publish release content (GTM: stories + articles, incl. the fourth story) | content | 32.21 | Four stories + article set published | #422 |
| 32.25 | Backfill WBS issue numbers + reconcile docs and GitHub | docs reconciliation | 32.21 | Every WBS row has its real issue number | #423 |
| 32.26 | Traceability (PRD 12) + glossary updates for v0.2.0 | docs | M25–M31 | Traceability map + glossary updated | #437 |
| 32.27 | Expanded release-gate verification | evidence | M29–M30, 32.2 | Items 9–16 of PRD 40 §5-expanded pass | #492 |
| 32.T | Add/expand test cases for this milestone | tests | release items | All new paths covered; coverage ≥ 95% | #386 |
| 32.D | Create/update the design + reference docs for this milestone | docs | release items | Docs updated and linked from the WBS | #387 |
| 32.R | Code review & risk sign-off for this milestone | review | 32.T + 32.D | Final sign-off recorded | #388 |

**Validation evidence (32.1–32.20)**

| Item | Evidence |
|---|---|
| 32.4 Security scan | `make security-scan` + `docs/release/v0.2.0/secret-scan-report.md` |
| 32.5 Audit | `docs/release/v0.2.0/security-audit.md` |
| 32.7 Artifacts | `docs/release/v0.2.0/release-evidence.md`; `make release-dry-run` |
| 32.9 First run | `docs/release/v0.2.0/first-run-evidence.md` |
| 32.15 Compliance | `docs/release/v0.2.0/compliance-matrix.md`; `reference/open-source-checklist.md` |
| 32.13 Reference | `reference/compatibility.md`; `known-limitations.md`; `docs/release/claims-ledger.json` |
| 32.27 Expanded gates | clean-OS timing (3 OSes); 2nd OTel backend; approval-v2; `ui` no-Docker; managed-policy; capability drift; commit→session; `suggest-policy` no-write; ASI rows; hold survival |

**Tests required:** full suite + coverage gate; release-gate suite (incl. expanded items); first-run timed test;
forward-compat matrix; naming install-guard test.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · WBS + issues updated · **all relevant documents
      updated** · pushed
- [ ] The [PRD 40](../../prd/40-v0.2.0-program.md) §5 release-gate criteria all pass at the release commit (including
      the expanded items 9–16)
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
all PRDs 40–59.

---

## v0.2.0 release gate (all milestones)

- [ ] M25–M32 exit criteria satisfied (incl. design docs + all relevant documents updated)
- [ ] PRD 40–59 scope delivered; cut-line items shipped or explicitly phased with re-pointed issues
- [ ] AAT third-party round-trip verified externally (CUJ-15); no "modeled" Tier-1 rows
- [ ] Streaming p99 ≤1 s (CUJ-17); cross-agent/host attribution (CUJ-16); compliance report offline (CUJ-18);
      detector numbers reproduced (CUJ-19); A2A delegation provable (CUJ-20)
- [ ] Expanded: no auto/bypass approval recorded as `user` (CUJ-21); commit→session + Agent Trace (CUJ-22);
      capability drift detected (CUJ-23); `ui` ≤60 s no Docker (CUJ-24); managed-policy truthful (CUJ-25);
      read-only MCP safe (CUJ-26); policy advisory only (CUJ-27); frameworks ≤2 lines (CUJ-28);
      outcomes deterministic (CUJ-29); runner segment verifies (CUJ-30); governance/hold/verifier (CUJ-31/32/8 ext.)
- [ ] `known-limitations.md` shrink verified (G1/G2/G4/G7/G8 removed with proving tests)
- [ ] Field tests pass; security scan + audit + SBOM/signing published; compliance matrix + Scorecard recorded
- [ ] Merged to main; **`v0.2.0` tagged and published (PyPI + npm)**; post-release install verified
- [ ] ADR-0026 naming outcome executed; claims ledger green; WBS issue numbers backfilled
