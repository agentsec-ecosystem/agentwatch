# M22 — Standards & Compliance Acceptance (PRD 39) Implementation Plan

**Goal:** Make compliance answerable: EU AI Act record-keeping (W1), real ISO/NIST appendices (W2), open
artifact standards (W3), pinned OTel semconv (W4), schema stewardship (W5), forensic soundness (W6),
checkpoint notarization (W7), OpenSSF/OSV readiness (W8), optional signed checkpoints (W9).

**Spec:** PRD [39](../prd/39-standards-and-compliance-acceptance.md) · WBS
[Part 13](../wbs/v0.1.0/wbs-v0.1.0-part13-compliance-acceptance.md) · issues #270–#278.

## Tasks

### Task 1 — W3 (#272): open artifact standards
- [x] `docs/compliance/standard-artifacts.md` pins OCSF 1.5.0 / CloudEvents 1.0 / CycloneDX 1.5 +
      lossless-or-explicit; test validates each output against its pinned version.

### Task 2 — W4 (#273): pin + publish the OTel GenAI semconv
- [x] `--version` carries the pinned semconv; `scripts/semconv_drift_check.py`; test.

### Task 3 — W5 (#274): schema stewardship
- [x] `schema/GOVERNANCE.md` + `schema/CHANGELOG.md`; `scripts/schema_policy_check.py` (a change without
      a changelog entry fails); test.

### Task 4 — W7/W9 (#276, #278): checkpoint export + optional signing
- [x] `notarize.py` (digest + optional RFC 3161 token), `signing.py` (ed25519, opt-in extra);
      `checkpoint export|verify`. Tests.

### Task 5 — W1/W2/W6/W8 (#270, #271, #275, #277): mappings + soundness + badge
- [x] `docs/compliance/*` mappings, `forensic.py` shipped in bundles, OpenSSF/advisory docs; tests.

### Task 6 — Docs, exit criteria
- [x] PRD 39, PRD 18, WBS M22, index, CLI reference, CHANGELOG.
- [x] One full gate: suite + coverage, ruff, mypy; commit; push; close #270–#278.

## Progress log

- 2026-10-03 — plan created; starting W3 (artifact standards).
- 2026-10-03 — all W1-W9 implemented; docs + tests added.
