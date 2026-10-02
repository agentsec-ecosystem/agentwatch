# Security Audit — v0.1.0 (template)

Status: **not started**.

## Scope

Code, dependencies, artifacts.

## Checks

- [ ] Dependency scan (pip-audit / osv-scanner) — clean
- [ ] Secret scan (trufflehog/gitleaks) — 0 verified
- [ ] Redaction attack pack — 0 secrets in store
- [ ] Export gating verified (blocked until self-test passes)
- [ ] Tamper tests (hook-config edit, store edit) — fail-closed
- [ ] Artifacts signed + SBOM published
- [ ] OpenSSF Scorecard grade recorded

## Findings

| # | Severity | Finding | Resolution |
|---|---|---|---|
