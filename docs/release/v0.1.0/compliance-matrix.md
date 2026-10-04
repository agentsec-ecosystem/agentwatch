# Compliance Matrix — v0.1.0

**BLUF:** agentwatch maps to recognized security/compliance frameworks; coverage is explicit, published,
and testable. We do not claim certifications we don't hold.

Status: **v0.1.0** · Spec: [PRD 18](../../prd/18-security-compliance.md) · OpenSSF: [open-source-checklist.md](../../reference/open-source-checklist.md)

## A. Product security controls

| Control | Standard ref | How agentwatch satisfies it | Evidence |
|---|---|---|---|
| No secrets at rest | OWASP LLM02 | Redaction-by-default before storage (DD-06); four privacy modes | `agentwatch verify-privacy`; M4 redaction tests |
| No secrets in source/history | OpenSSF; OWASP | gitleaks + trufflehog scan of first-party code and full history | [secret-scan-report.md](secret-scan-report.md) |
| Tamper-evident records | NIST SSDF; SOC 2 CC7 | Hash-chained append-only store (DD-07); chain checkpoints | `verify-store`; F4 fault test; `tests/test_store_hardening.py` |
| Fail-closed, never silent | NIST SSDF; SOC 2 CC7 | Failures surface via `/healthz`, never silent stop (NFR-8) | `tests/test_fault_injection.py` (F1–F10) |
| Local-first, opt-in egress | OWASP LLM02 | No network by default; export gated on self-test (DD-09) | `scripts/offline_e2e.py`; `tests/test_egress_audit.py` |
| Least-privilege posture | OWASP ASVS | Store dir 0700, files 0600, socket 0600 | `agentwatch.posture`; posture tests |
| Supply-chain integrity | OpenSSF Scorecard; SLSA | SBOM + checksums + signed provenance; DCO; pinned deps | `.github/workflows/release.yml`; `scripts/release/` |
| Vulnerability disclosure | CVE norm | Org SECURITY policy; private advisories | `SECURITY.md` |
| Self-health visible | SOC 2 CC1/CC7 | `/healthz` + `agentwatch status` (PRD 13) | `tests/test_health.py` |
| Durability is explicit | NIST SSDF | `store.durability` modes surfaced in `/healthz` | `tests/test_store_hardening.py` |

## B. Framework coverage (published, honest)

| Framework | Coverage | Notes |
|---|---|---|
| OWASP Top 10 for LLM Apps 2025 | **LLM02** (sensitive-info disclosure), **LLM05** (improper output handling); partial **LLM06** (excessive agency: *records* tool calls; enforcement is agentpolicy) | Record/redact/local-first |
| NIST AI RMF + GenAI Profile | **Manage** function: records + audit trail + evidence export | Controls-mapping appendix |
| NIST SSDF (SP 800-218) | Secure dev: DCO, branch ruleset, SBOM, signed releases, Scorecard | OpenSSF checklist |
| ISO/IEC 42001 | Controls-mapping appendix for enterprise buyers | Not certified in v1 |
| SOC 2 | Type I/II **evidence source** — agentwatch's own audit log is the pipeline | Type I post-traction |
| OpenSSF Scorecard / Best Practices | Workflow runs; SBOM + signed provenance | [open-source-checklist.md](../../reference/open-source-checklist.md) |

## C. Explicitly not claimed

- **Not a certified product (v1):** SOC 2 Type I/II, ISO 27001 are post-traction. We say so.
- **Not an injection/intent classifier:** OWASP LLM01 mitigation is isolation/enforcement (agentpolicy),
  not detection.
- **No ML in the enforcement path:** LLM-augmented detectors are observability signals, not controls.
- **No FIPS/Common Criteria** in v1 (OS-native crypto; FIPS-mode is a platform claim).

## Verification

- Full package gate: `make test` (coverage ≥95%, ruff zero, mypy strict).
- Fault-injection F1–F10: `tests/test_fault_injection.py`.
- Offline/local-first proof: `.github/workflows/offline-e2e.yml` + `scripts/dependency_egress_audit.py`.
- Parity gate (PRD 10 A1–A6): `scripts/check_parity.py` (run in `tests/test_parity.py`).
