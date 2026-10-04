# Security Audit — v0.1.0

**BLUF:** A **self-audit** with control→test evidence; every applicable item is backed by an automated
test. An **external** audit and Sigstore signing of the published artifacts are release-time actions.

Status: **published** (M24 24.3) — self-audit complete with field-test evidence; external audit + Sigstore signing of the published artifacts are release-time actions (see residual risk).

## Scope

Code (`packages/`, `services/`, `apps/`), dependencies, and artifacts. Spec: [PRD 18](../../prd/18-security-compliance.md).

## Checks

| Check | Result | Evidence |
|---|---|---|
| Redaction attack pack — 0 secrets in store | ✅ | `agentwatch verify-privacy`; `tests/test_secrets.py`, `tests/test_redact.py` |
| Redaction self-test gates export (DD-09) | ✅ | `tests/test_selftest.py`; `tests/test_export.py` |
| Tamper (store edit) → fail-closed | ✅ | `tests/test_store_hardening.py`, `tests/test_fault_injection.py` (F4) |
| Tamper (chain mid-session) → surfaces | ✅ | `store.refresh()` in the daemon sweep; `tests/test_store_hardening.py` |
| Fault-injection F1–F10 fail closed | ✅ | `tests/test_fault_injection.py` |
| No egress-capable runtime imports | ✅ | `scripts/dependency_egress_audit.py`; `tests/test_egress_audit.py` |
| Offline record→verify→replay | ✅ | `scripts/offline_e2e.py`; `.github/workflows/offline-e2e.yml` |
| Least-privilege file posture (0700/0600) | ✅ | `agentwatch.posture`; `tests/test_store_hardening.py` |
| Schema reject-never-coerce (F8) | ✅ | `tests/test_records.py`, `tests/test_schema_contract.py` |
| Dependency scan (pip-audit / osv-scanner) | ✅ 0 known vulns; CI (Dependabot + Scorecard) | `make security-scan` → [`security-scan/pip-audit-*.json`](security-scan/); `.github/workflows/` |
| Secret scan (gitleaks/trufflehog) — first-party, incl. history | ✅ 0 real; 5 intentional placeholders | [secret-scan-report.md](secret-scan-report.md); [`.gitleaks.toml`](../../../.gitleaks.toml) |
| Artifacts signed + SBOM published | ✅ dry-run verified; CI signs on tag | [release-evidence.md](release-evidence.md); `scripts/release/`, `.github/workflows/release.yml` |
| OpenSSF Scorecard grade recorded | 🤖 per release | `scorecard.yml` |
| Field-test recorder evidence (fresh install, replay, tamper, redaction) | ✅ | [FIELD_TEST_REPORT](../../field-test/v0.1.0/FIELD_TEST_REPORT.md); FT-01…FT-06, FT-04 |
| Hash chain intact under a 10k-hook soak | ✅ | FT-28: 10000/10000 delivered, `verify-store` green, p99=0.36 ms |

## Findings

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | Info | Docs referenced a wrong PydanticAI symbol (`trace_agent_pydantic`) | Fixed → `trace_pydantic_agent`; guarded by the parity gate |
| 2 | Low | Continuous chain verification is O(n) per sweep, not O(1) amortized | Lock-hold reduced to O(1) by the snapshot-then-verify fix (field test D-1), so the sweep no longer blocks the accept path; total verify cost remains O(n). Documented in [known-limitations](../../reference/known-limitations.md); correctness-first |
| 3 | Low | HTTP MCP proxy buffers each forwarded response in memory | Documented in [known-limitations](../../reference/known-limitations.md) |
| 4 | Info | `EmbeddingDriftDetector` silently returned `None` on every call because the configured LLM server exposed no embedding model | Fixed: chat-based similarity fallback (field test D-4); deep check `llm_called_ok` now guards it |

**Unresolved findings: 0.**

## Residual risk (stated, not hidden)

- No external penetration test in v0.1.0 (post-traction).
- Hash chain is detect-only; no signing key at v0.1.0.
- Sigstore signing of published artifacts is CI-managed and requires a tag; see [versioning-policy](../../reference/versioning-policy.md).
