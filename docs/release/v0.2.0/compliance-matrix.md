# Compliance Matrix — v0.2.0

**BLUF:** agentwatch maps to recognized security/compliance frameworks; coverage is explicit, published, and
testable. We do not claim certifications we don't hold.

Status: **v0.2.0** · Spec: [PRD 18](../../prd/18-security-compliance.md) · OpenSSF:
[open-source-checklist.md](../../reference/open-source-checklist.md) · Security: [security-audit.md](security-audit.md).

## A. Product security controls

| Control | Standard ref | How agentwatch satisfies it | Evidence |
|---|---|---|---|
| No secrets at rest | OWASP LLM02 | Redaction-by-default before storage (DD-06); four privacy modes | `agentwatch verify-privacy`; `test_secrets.py`, `test_redact_eval.py`, `test_redaction_properties.py` |
| No secrets in source/history | OpenSSF; OWASP | gitleaks + trufflehog over first-party code and full history | [secret-scan-report.md](secret-scan-report.md) |
| Tamper-evident records | NIST SSDF; SOC 2 CC7 | Hash-chained append-only store (DD-07); chain checkpoints | `verify-store`; `test_store_hardening.py`; FT-BACKEND-2 |
| Fail-closed, never silent | NIST SSDF; SOC 2 CC7 | Failures surface via `/healthz`, never a silent stop (NFR-8) | `test_fault_injection.py` (F1–F10) |
| Local-first, opt-in egress | OWASP LLM02 | No network by default; export gated on self-test (DD-09) | `scripts/offline_e2e.py`; `test_egress_audit.py` |
| Least-privilege posture | OWASP ASVS | Store dir 0700, files 0600, socket 0600 | `agentwatch.posture`; posture tests |
| Role × data-class access model | NIST least-privilege; PRD 56 | cross-role read returns nothing and is recorded; least-privilege default | `test_access.py` (FT-ACC-1) |
| Supply-chain integrity | OpenSSF Scorecard; SLSA | SBOM + checksums + Sigstore + build provenance; DCO; pinned deps | `.github/workflows/release.yml`; `scripts/release/`; [release-evidence.md](release-evidence.md) |
| Dependency hygiene | OpenSSF | permissive licences only; 0 known vulns | [dependency-review.md](dependency-review.md); `pip-audit` |
| Vulnerability disclosure | CVE norm | Org SECURITY policy; private advisories | `SECURITY.md` |
| Self-health visible | SOC 2 CC1/CC7 | `/healthz` + `agentwatch status` (PRD 13) | `test_health.py` |
| Capability supply chain | OWASP ASI (skill/plugin supply chain) | capability inventory + content-digest drift; Plugin4Shell class detected | `test_capability_drift.py` (FT-CAP-1) |
| Agent identity / credential class | NIST CAISI; PRD 44 | `credential_class` exported; ambient/shared flagged; absent never invented | `test_credential_hygiene.py` (FT-IDN-3) |
| Verification without install | PRD 57 | offline browser verifier: zero-network; verdicts equal CLI; tampered bundle names the break | `test_browser_verifier.py` (FT-VFY-1) |

## B. Framework coverage (published, honest)

| Framework | Coverage | Notes |
|---|---|---|
| **OWASP Agentic (ASI) 2026 + AST10** | **all 10 ASI rows + AST10** published with per-row evidence, no prevention claim; every evidenced command runs | `agentwatch compliance report --framework owasp-asi-2026`; `test_compliance_asi.py` (FT-ASI-1) |
| OWASP Top 10 for LLM Apps | **LLM02**, **LLM05**; partial **LLM06** (records tool calls; enforcement is agentpolicy) | record/redact/local-first |
| NIST AI RMF + GenAI Profile | **Manage**: records + audit trail + evidence export | controls mapping |
| NIST SSDF (SP 800-218) | DCO, branch ruleset, SBOM, signed releases, Scorecard | OpenSSF checklist |
| ISO/IEC 42001 · ISO 27001 · SOC 2 · NIST 800-92 · EU AI Act Art.12 | offline report templates with per-row evidence | `test_compliance.py`, `test_compliance_docs.py` (FT-CMP-1/3) |
| OCSF 1.5.0 + Syslog | OCSF reference consumer + Syslog sink with the redaction gate | `test_siem_consumers.py`, `test_siem_syslog.py` (FT-SIEM-1) |
| OpenSSF Scorecard / Best Practices | workflow runs on `main`; grade recorded per release | [open-source-checklist.md](../../reference/open-source-checklist.md) |

## C. Explicitly not claimed

- **Not a certified product (v0.2.0):** SOC 2 Type I/II, ISO 27001 are post-traction. We say so.
- **Not an injection/intent classifier:** OWASP LLM01 mitigation is isolation/enforcement (agentpolicy), not detection.
- **No ML in the enforcement path:** LLM-augmented detectors are observability signals, not controls.
- **No FIPS/Common Criteria** (OS-native crypto; FIPS-mode is a platform claim).
- **Windows unsupported** (FT-WIN-1 N/A).

## Verification

- Full package gate: `make test` (coverage ≥95%, ruff zero, mypy strict) + repo guard.
- Fault-injection F1–F10: `test_fault_injection.py`.
- Offline/local-first: `.github/workflows/offline-e2e.yml` + `scripts/dependency_egress_audit.py`.
- Field test: [FIELD_TEST_REPORT](../../field-test/v0.2.0/FIELD_TEST_REPORT.md) (92 PASS · 0 FAIL).

## Scorecard grade

The **OpenSSF Scorecard** workflow (`.github/workflows/scorecard.yml`) runs on `main` and on a weekly schedule
with `publish_results: true`; the grade is published on the repository badge and recorded per release. The grade
is **not claimable from this branch** (Scorecard grades `main`); it is recorded at release readiness on `main`.
