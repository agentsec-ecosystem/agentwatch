# Reference — Open-Source Readiness Checklist

**BLUF:** Mapping to OpenSSF Best Practices / Scorecard, tracked per release.

| Item | Status |
|---|---|
| LICENSE (Apache-2.0) | ✅ |
| README | ✅ |
| CHANGELOG | ✅ |
| CONTRIBUTING (org) | ✅ |
| CODE_OF_CONDUCT (org) | ✅ |
| SECURITY policy | ✅ |
| Issue/PR templates | ✅ |
| DCO enforcement | ✅ |
| Branch ruleset (PR required) | ✅ |
| Secret scanning + push protection | ✅ | [`secret-scan-report.md`](../release/v0.1.0/secret-scan-report.md) — gitleaks + trufflehog + pip-audit; 0 real first-party findings |
| Dependabot alerts | ✅ |
| OpenSSF Scorecard workflow | ✅ (grade recorded per release) |
| Signed releases + SBOM + provenance | ✅ (`.github/workflows/release.yml`, `scripts/release/`; local dry-run: `make release-dry-run`) |
| Release notes + security audit per version | ✅ (`docs/release/v0.1.0/`) |

Gold target: Scorecard grade A, OpenSSF Best Practices passing badge.
