# v0.2.0 — M31 (Field Tests) Code Review Log

Record of the M31 field-test review and risk sign-off (issue #385). One row per finding; closed when
fixed + tested. Declared / waived items carry a reason.

**Scope reviewed:** the M31 field-test work items (#408, #409, #410, #389, #390, #391, #392, #393, #394,
#395, #383, #384, #488–#491) and the published report `docs/field-test/v0.2.0/FIELD_TEST_REPORT.md`.

## Field-test outcome

- 94/94 v0.2.0 cases accounted for: **92 PASS · 0 FAIL · 1 not run (declared FT-XHT-2) · 1 N/A (FT-WIN-1)**.
- **90 of the 92 PASS are grounded** — each asserts its plan condition (a shipped repo test where one exists,
  else a strengthened recorder driver). The hardening campaign is recorded in the report
  (patterns A–D, batches, per-case notes, running progress log).
- 2 PASS remain run-only but **blocked on tooling absent in this environment**: **FT-LG-1** (needs a real
  LangGraph / raw-Python SDK driver) and **FT-XHT-3** (needs two independent OSS parsers). Flagged, never faked.
- FT-XHT-2 is a **declared** `P/F|D` case (no OpenCode binary in the recorder image) — a declaration is not a
  pass. FT-WIN-1 is **N/A** (Windows unsupported, retired).

## Findings

| # | Ticket | Finding | Severity | Resolution | Status |
|---|---|---|---|---|---|
| 1 | FT-BACKEND-2 (R4) | The Tempo second OTLP backend was never started and the collector exported only to Jaeger; the old `|| true` hid it | High | `tempo` added to `V020_PROFILE_SERVICES` (`scripts/fieldtest/lib.sh`); `otlp/tempo` exporter + fan-out in `deploy/otel-collector-config.yml`; field case re-run green | Fixed |
| 2 | FT-MATRIX-1 / FT-XHT-4 | `gemini-cli` was a Tier-1 `modeled` row (violates PRD 40 §5.3) | High | new `HarnessInfo.declared` flag; `gemini-cli` set `declared=True`; `scripts/check-matrix-tiers.py` gate; guarded by `test_compatibility.py` | Fixed |
| 3 | FT-LUI-1 | The local console page had no `<main>` landmark (axe `landmark-one-main`, `region`) | Medium | page wrapped in `<main>`; guarded by `apps/web/tests/e2e/console.spec.ts` + `a11y.spec.ts` | Fixed |
| 4 | FT-COR-2 / FT-CAP-2 / FT-PRV-2 | Drivers ran against an empty store (`E_SESSION_NOT_FOUND`) | Low (harness) | seed `ft04` (`ft_emit --corpus secrets`); re-run green | Fixed |
| 5 | FT-STR-2 | Soak "over-delivery" — a harness artifact (the soak ran against the recorder's non-empty store) | Low (harness) | run the soak against a fresh temp store → `within_bounds=True` | Fixed |

## Guardrails honored

- **Monitor-only** (blocking hooks recorded, never answered) — `test_permission_mode.py`, `test_authorization.py`.
- **Redaction before storage / no secrets committed** — `test_redact_eval.py`, `test_secret*`, redaction corpus.
- **Foreign content never executed** — `test_fuzz_parsers.py`, `test_testkit_corpus.py`.
- **Local-first / no egress** — `test_egress_audit.py`, offline compliance (`test_compliance.py`).
- **Deterministic trust path** — chain verification, `test_browser_verifier.py` (offline parity), `test_store_vectors.py`.
- **A `declared` case is never reported as "done"** — FT-XHT-2 carries `declared:true` with a named limitation.

## Standard milestone-end gates

| Gate | Result |
|---|---|
| Field-test suites (local, Docker Compose, per-case `down -v`) | **92 PASS · 0 FAIL · 1 declared · 1 N/A** |
| Shipped unit/differential tests run during this pass (SDK + analytics + api contract) | pass (see the report's Hardening progress log) |
| `detector-eval` CI workflow | **OPEN (pre-existing, not field-test):** the workflow runs `scripts/detector_eval.py`, which reads `services/analytics/data/detector-corpus-v0.json` — a **gitignored** file (`.gitignore` → `data/`) that `scripts/generate_detector_corpus.py` generates. The workflow never generates it, so it is red on the branch. Carried to **M32** (release readiness). |
| `Security Scan` (security.yml) CI workflow | **OPEN (pre-existing):** GitHub reports a workflow-file issue on the branch; carried to **M32**. |

## Risk sign-off (M31)

Reviewed the field-test evidence per suite; every field-test defect has a fix and a re-run (findings 1–5);
CUJ-15–34 verification is recorded in the report; anything not run is stated (FT-XHT-2 declared, FT-WIN-1 N/A,
FT-LG-1 / FT-XHT-3 blocked). No unresolved field-test review findings. The two open CI items above are
**outside the field-test scope** and are explicitly carried to the v0.2.0 release-readiness milestone (M32) —
they are not claimed green here.
