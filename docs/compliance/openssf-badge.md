# OpenSSF Best Practices badge — self-assessment

Target: **passing** tier before v0.1.0 (the gold path is tracked for post-v0.1.0).
Each criterion is listed met or gap; the release gate re-checks it.

| Criterion | Status | Evidence |
|---|---|---|
| Public source repository | ✅ met | `agentsec-ecosystem/agentwatch` |
| OSI-approved license | ✅ met | `LICENSE` |
| Basic project website / docs | ✅ met | `README.md`, `docs/` |
| Contribution process | ✅ met | `CONTRIBUTING.md`, DCO |
| Code of conduct | ✅ met | `CODE_OF_CONDUCT.md` |
| Security policy | ✅ met | `SECURITY.md` |
| Vulnerability reporting process | ✅ met | `SECURITY.md`, see [advisory-process.md](advisory-process.md) |
| Automated tests on changes | ✅ met | CI runs the SDK suite |
| Static analysis / lint | ✅ met | `ruff`, `mypy --strict` in CI |
| Build/release provenance | ✅ met | `verify-release`, CycloneDX SBOM, cosign/SLSA |
| Documented code-review (CODEOWNERS) | ✅ met | `.github/CODEOWNERS` |
| Two-factor for maintainers | ⚠️ gap | organizational, tracked for release |
| Reproducible build | ⚠️ gap | documented as best-effort; tracked for release |
| Dependencies monitored for vulns | ✅ met | OSV registration (see advisory process), Scorecard |

## Notes

The badge is re-checked at the **M24 release gate**; drift after achievement is a
release blocker, not a silent lapse.
