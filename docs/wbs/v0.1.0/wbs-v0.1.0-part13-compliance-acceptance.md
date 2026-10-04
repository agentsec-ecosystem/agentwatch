# WBS v0.1.0 — Part 13: Compliance Acceptance (M22)

**BLUF:** Make the compliance story answerable by a buyer, an auditor, and an opposing expert. PRDs 31–39, all in v0.1.0. Field Tests (M23) and Release Readiness (M24) remain the last two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M22 — Standards & Compliance Acceptance (PRD 39)

**Status:** ✅ complete

**Goal:** Make compliance answerable: EU AI Act record-keeping, ISO/NIST appendices, open artifact standards, pinned OTel semconv, schema stewardship, forensic soundness, checkpoint notarization/signing, and OpenSSF/OSV readiness.

**Requirements / PRDs:** [PRD 39](../../prd/39-standards-and-compliance-acceptance.md) · full detail in the PRD sections.

**Work items**

| # | Task | Deliverable | Acceptance | Issue |
|---|---|---|---|---|
| 22.W1 | EU AI Act record-keeping mapping (Art. 12, Art. 19, Art. 26) | mapping/docs + conformance | Link-check | #270 ✅ |
| 22.W2 | Make the ISO/IEC 42001 and 27001 appendices real | mapping/docs + conformance | Link-check | #271 ✅ |
| 22.W3 | Align with the open artifact standards instead of inventing shapes | mapping/docs + conformance | Each output validates against its pinned standard schema | #272 ✅ |
| 22.W4 | Pin and publish the OTel GenAI semconv version, and upstream | mapping/docs + conformance | Exported resource attributes carry the pinned version | #273 ✅ |
| 22.W5 | Schema stewardship as published policy | mapping/docs + conformance | A schema change without a changelog entry fails the policy check | #274 ✅ |
| 22.W6 | A forensic-soundness statement | mapping/docs + conformance | Link-check | #275 ✅ |
| 22.W7 | Optional checkpoint notarization | mapping/docs + conformance | `checkpoint export` emits a digest | #276 ✅ |
| 22.W8 | OpenSSF Best Practices badge and OSV/advisory readiness | mapping/docs + conformance | The badge self-assessment is complete | #277 ✅ |
| 22.W9 | Optional signed checkpoints | mapping/docs + conformance | A signed checkpoint verifies with its public key | #278 ✅ |

**Tests required:** per-item tests as listed; all new paths covered; coverage ≥ 95%.

**Exit criteria**

- [x] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated
- [x] Every mapped control names an evidence command; forensic-soundness statement shipped in bundles.

**Design docs to update:** [PRD 39](../../prd/39-standards-and-compliance-acceptance.md), [PRD 18](../../prd/18-security-compliance.md) — updated; mappings in [docs/compliance/](../../compliance/) and [forensic-soundness.md](../../design/forensic-soundness.md).

---
