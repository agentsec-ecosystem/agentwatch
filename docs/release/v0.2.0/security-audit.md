# Security Audit — v0.2.0

**BLUF:** A **self-audit** with control→test evidence; every applicable item is backed by an automated test or a
field-test case. An **external** audit and Sigstore signing of the published artifacts are release-time actions.

Status: **published** (M32 32.5) — self-audit complete with field-test evidence; external audit + Sigstore signing
of the published artifacts are release-time actions (see residual risk). **Unresolved findings: 0.**

## Scope

Code (`packages/`, `services/`, `apps/`), dependencies, and artifacts. Spec:
[PRD 18](../../prd/18-security-compliance.md). Release gate: [PRD 40 §5](../../prd/40-v0.2.0-program.md).

## Checks

| Check | Result | Evidence |
|---|---|---|
| Redaction attack pack — 0 secrets in store | ✅ | `agentwatch verify-privacy`; `tests/test_secrets.py`, `test_redact.py`, `test_redaction_properties.py` |
| Redaction eval — per-class recall/FP published, deterministic offline | ✅ | `test_redact_eval.py`; `schema/vectors/redaction/` |
| Redaction self-test gates export (DD-09) | ✅ | `tests/test_selftest.py`; `tests/test_export.py` |
| Tamper (store edit) → fail-closed | ✅ | `tests/test_store_hardening.py`, `test_fault_injection.py` (F4) |
| Fault-injection F1–F10 fail closed | ✅ | `tests/test_fault_injection.py` |
| No egress-capable runtime imports | ✅ | `scripts/dependency_egress_audit.py`; `tests/test_egress_audit.py` |
| Offline record→verify→replay | ✅ | `scripts/offline_e2e.py`; `.github/workflows/offline-e2e.yml` |
| Offline browser verifier — zero-network page, verdicts equal CLI on the fixture set; tampered bundle names the first broken link | ✅ | `tests/test_browser_verifier.py` |
| Least-privilege file posture (0700/0600) | ✅ | `agentwatch.posture`; `tests/test_store_hardening.py` |
| Schema reject-never-coerce (F8) | ✅ | `tests/test_records.py`, `test_schema_contract.py` |
| **Access model — cross-role read returns nothing and is recorded; least-privilege default** | ✅ | `tests/test_access.py` (FT-ACC-1) |
| **Identity — credential class exported; ambient/shared flagged; absent never invented** | ✅ | `tests/test_credential_hygiene.py`, `test_identity.py` (FT-IDN-1/3) |
| **Console — loopback-only, token-gated, read-only, no egress** | ✅ | `tests/test_console.py` (FT-LUI-1) |
| **Derived index — purge/retention propagate; index rebuildable, content-free** | ✅ | `tests/test_query_index.py`, `test_purge_propagation.py` (FT-LUI-2) |
| **Capability supply chain — Plugin4Shell content-changed/version-unchanged detected** | ✅ | `tests/test_capability_drift.py` (FT-CAP-1) |
| **Sandbox boundary — % unsandboxed + denials by class; unknown counted** | ✅ | `tests/test_sandbox_events.py` (FT-SBX-1) |
| **Legal hold — held records survive retention, purge, index rebuild** | ✅ | `tests/test_legal_hold.py` (FT-HLD-1) |
| **Authorization — no auto/bypass misreported as `user`; classifier never user/rule** | ✅ | `tests/test_authorization.py`, `test_permission_mode.py`, `test_oversight.py` (FT-APV-1/2/3) |
| Dependency scan (pip-audit) | ✅ 0 known vulns | [`security-scan/pip-audit-*.json`](security-scan/); `make security-scan` |
| Secret scan (gitleaks/trufflehog) — first-party, incl. history | ✅ 0 real; 5 intentional placeholders | [secret-scan-report.md](secret-scan-report.md); [`.gitleaks.toml`](../../../.gitleaks.toml) |
| Artifacts signed + SBOM published | ✅ dry-run verified; CI signs on tag | `scripts/release/`, `.github/workflows/release.yml`; 32.1/32.7 |
| OpenSSF Scorecard grade recorded | 🤖 per release | `.github/workflows/scorecard.yml` |
| Field-test recorder evidence (fresh install, replay, tamper, redaction, hostile input) | ✅ | [FIELD_TEST_REPORT](../../field-test/v0.2.0/FIELD_TEST_REPORT.md); 92 PASS / 0 FAIL |
| Hash chain intact under a 10k-hook soak | ✅ | FT-STR-2: fresh-store soak `within_bounds=True` |

## Findings

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | Info | `gemini-cli` was presented as a Tier-1 `modeled` row (a fidelity over-claim, not a code defect) | Fixed: `HarnessInfo.declared`; `check-matrix-tiers.py` gate (FT-MATRIX-1/FT-XHT-4) |
| 2 | Info | Secret scan initially flagged synthetic `sk-abcdefgh1234` fixtures + the ephemeral console token in committed field-test evidence | Fixed: allowlisted by path (fixtures + `field-test/**`) in `.gitleaks.toml`; documented in [secret-scan-report.md](secret-scan-report.md) |
| 3 | Low | The security-scan script wrote evidence to `docs/release/v0.1.0/` | Fixed: default output is now `docs/release/v0.2.0/security-scan/` |

**Unresolved findings: 0.**

## Residual risk (stated, not hidden)

- **No external penetration test** in v0.2.0 (planned post-traction).
- The hash chain is **detect-only**; there is no signing key on the record path (integrity is by hash-chain +
  optional checkpoint signatures).
- **Sigstore signing + SLSA provenance** of the published artifacts are CI-managed and require a `v*` tag; the
  local dry-run validates everything verifiable without an OIDC identity (32.1/32.7).
- **Windows is unsupported** (FT-WIN-1 N/A); the clean-machine 3-OS timing gate is partial (see the
  [release checklist](release-checklist.md) gate 9).
