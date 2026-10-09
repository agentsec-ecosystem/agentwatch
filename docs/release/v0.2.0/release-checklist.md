# v0.2.0 — Release Checklist & Go/No-Go

Item **32.2** (issue #411). Every PRD 40 §5 gate (1–8) and §5-expanded gate (9–16) is listed with its status and
the evidence that proves it. This is the go/no-go record for v0.2.0.

- **Release:** v0.2.0 (`feat-v0.2.0` → `main`)
- **Field-test report:** [`docs/field-test/v0.2.0/FIELD_TEST_REPORT.md`](../../field-test/v0.2.0/FIELD_TEST_REPORT.md)
  — 94/94 cases: **92 PASS · 0 FAIL · 1 not run (declared FT-XHT-2) · 1 N/A (FT-WIN-1)**; 90/92 grounded.
- **Status legend:** ✅ pass · ⚠️ partial/declared · ⛔ not met.

## PRD 40 §5 gates

| # | Gate | Status | Evidence |
|---|---|---|---|
| 1 | `export-session --format aat` validates against published fixtures; a third-party AAT consumer round-trips it (CUJ-15) | ✅ | FT-AAT-1 (independent `schema/vectors/verify_aat.py`), FT-AAT-2/3 |
| 2 | `known-limitations.md` shrinks — G1/G2/G4/G7/G8 leave with their proving test | ✅ | FT-CLAIM-1 (claims ledger backed + generated table); G1→FT-STR-1, G2→FT-TRACE-1, G4→FT-DET-2, G7→FT-OTEL-1/2, G8→FT-CMP-2 |
| 3 | Compatibility matrix has no "modeled" Tier-1 rows; every row `live-verified \| fixture-verified` | ✅ | FT-MATRIX-1 / FT-XHT-4 (`check-matrix-tiers.py`, `test_compatibility.py`) |
| 4 | Detector precision/recall published against a versioned public corpus; ≥80% of rule detectors non-silent | ✅ | FT-DET-1/3/4/6/7 (shipped eval), FT-DET-2 (≥80% gate), FT-COR-1 (second corpus) |
| 5 | `compliance report --framework eu-ai-act-art12` runs offline, citing bundle-verifiable evidence (CUJ-18) | ✅ | FT-CMP-1 (`test_compliance.py` + `test_compliance_docs.py`) |
| 6 | Streaming p99 hook→operator-view ≤ 1 s | ✅ | FT-STR-1 (real p99), FT-STR-2 (fresh-store soak) |
| 7 | Agent identity + approval provenance answerable in one command across a multi-agent trace (CUJ-14/16) | ✅ | FT-IDN-1 (fleet-run), FT-IDN-2/3 |
| 8 | Field-test report published (FLD-1); claims ledger green | ✅ | this report; FT-CLAIM-1 |

## PRD 40 §5-expanded gates (PRD 49–59)

| # | Gate | Status | Evidence |
|---|---|---|---|
| 9 | Clean-machine timing published for macOS, Linux, Windows (closes R2 "partial") | ⚠️ **partial** | FT-ENV-0 (timed: macOS; ≤900 s budget enforced). **Windows unsupported → FT-WIN-1 N/A (retired).** R2 Windows leg is a declared limitation, not a pass. |
| 10 | Two OTel backends proven (closes R4 "partial") | ✅ | FT-OTEL-1 (tree in Jaeger **and** Tempo), FT-BACKEND-2 (Tempo backend fixed + fan-out) |
| 11 | No Claude Code call under auto/bypass reported as `user`; `approval` v2 live (CUJ-21) | ✅ | FT-APV-1/2/3 (`test_authorization.py`, `test_permission_mode.py`, `test_oversight.py`) |
| 12 | `agentwatch ui` demonstrated from a clean install with no Docker (CUJ-24) | ✅ | FT-LUI-1 (console Playwright + axe; no Docker) |
| 13 | Managed-policy install verified on a real managed config, or declared unverified (CUJ-25) | ✅ | FT-DEP-1 (`doctor_managed.py` — never reports installed while blocked) |
| 14 | Plugin4Shell-shape capability drift detected (CUJ-23); commit resolves to a session; Agent Trace export validates (CUJ-22) | ✅ | FT-CAP-1, FT-PRV-1 (`test_provenance.py`), FT-PRV-2 |
| 15 | `suggest-policy`/`what-if` write nothing outside `--out`; `owasp-asi-2026` every row runs (CUJ-27, CUJ-18 ext.) | ✅ | FT-POL-1 (`test_policy_suggest.py`/`test_policy_whatif.py`), FT-ASI-1 (`test_compliance_asi.py`) |
| 16 | Held records survive retention, purge, and index rebuild (CUJ-32) | ✅ | FT-HLD-1 (hold_lifecycle) |

## Standard milestone-end gates

| Gate | Status | Evidence |
|---|---|---|
| Whole-repo test suite + coverage ≥ 95% on the release commit | ⏳ pending (32.8) | run at the release commit |
| `ruff` zero · `mypy --strict` clean | ⏳ pending (32.8) | run at the release commit |
| `make security-scan` clean (secrets + deps + egress) | ⏳ pending (32.4) | `docs/release/v0.2.0/secret-scan-report.md` |
| `make release-dry-run` (build + SBOM + checksums + verify-release) | ✅ | 32.1 — `ok: true` |

## Go/No-Go

**Decision: GO (conditional).**

- 15 of the 16 PRD 40 §5 / §5-expanded gates pass at the field-test commit; the one exception is gate **9
  (clean-machine 3-OS timing)** — macOS timed, Windows unsupported (**FT-WIN-1 N/A**, a declared limitation), so R2
  closes **excluding Windows**.
- Conditions to clear before 32.20 (merge to main): **32.4** security scan and **32.8** full suite + coverage + lint
  must be green on the release commit. Note two **pre-existing** CI jobs are currently red on the branch and must be
  fixed or recorded: `detector-eval` (gitignored corpus — generate it in the workflow) and `security.yml`
  (workflow-file issue). See `docs/wbs/v0.2.0/codereview-log-m31.md`.

## Sign-off

| Role | Name | Decision | Date |
|---|---|---|---|
| Maintainer / release owner | deghosal-2026 | GO (conditional, gate 9 declared) | 2026-10-09 |
