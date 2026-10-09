# Secret Scan Report — v0.2.0 (M32 32.4)

**BLUF:** agentwatch's own source (code, docs, scripts, workflows, git history) contains **0 real secrets**.
Three independent checks (gitleaks, trufflehog, egress) pass; `pip-audit` reports **0 known vulnerabilities**.
Reproduce with `make security-scan`. Third-party ported example code, committed field-test evidence, and the
public redaction corpus are scoped out by an explicit, reviewed allowlist — not hidden.

## Scope

- **In scope:** first-party source — `packages/`, `services/`, `apps/`, `scripts/`, `docs/`, `.github/`, and the
  full git history of the repository.
- **Out of scope (allowlisted, with reason):**
  - `m13-agents/**` — ported predecessor example agents (third-party; not agentwatch source).
  - Intentional secret material used to test redaction / the self-test:
    `packages/python-sdk/src/agentwatch/selftest.py` (`MIIEowSECRETMATERIAL`),
    `packages/python-sdk/tests/test_secrets.py`, `test_redaction_properties.py`, `_secret_oracle.py`,
    `test_aat_ingest.py`, `test_gemini_ingest.py`, `test_m25_integration.py`,
    `packages/python-sdk/tests/fixtures/ingest/otel_trace.json`, and the field fixture
    `scripts/fieldtest/fixtures/otel/otel_trace.json` (all use the synthetic `sk-abcdefgh1234`). These fixtures
    **must exist** — they prove the redactor catches real token shapes.
  - `schema/vectors/redaction/**` — the public redaction corpus (synthetic, fabricated secret-shaped values).
  - `field-test/**` — committed field-test evidence (ephemeral per-run keys such as the loopback console token
    and `flow.key`/`signing.key`; decrypted stores that intentionally contain test secrets).
  - `docs/release/v0.1.0/security-scan/` and `docs/release/v0.2.0/security-scan/` — committed scan output (it
    contains the fixture matches it reports on).

The allowlist is committed as [`.gitleaks.toml`](../../../.gitleaks.toml); the trufflehog path excludes are
committed as [`scripts/security/trufflehog-exclude.txt`](../../../scripts/security/trufflehog-exclude.txt).

## Tools & commands

Run everything with `make security-scan` (or `bash scripts/security_scan.sh`). Evidence is written to
[`security-scan/`](security-scan/).

| Tool | Version | Command | Result |
|---|---|---|---|
| gitleaks | 8.30.1 | `gitleaks detect --config .gitleaks.toml` (git history, 244 commits) | **no leaks found** |
| trufflehog | 3.97.4 | `trufflehog filesystem packages services apps scripts docs .github --no-update --no-verification --json -x scripts/security/trufflehog-exclude.txt` | 5 **unverified** findings — all intentional fixtures (below) |
| pip-audit | 2.10.1 | `pip-audit <pkg> --format json` for `packages/python-sdk`, `services/api`, `services/analytics` | **no known vulnerabilities** |
| egress audit | — | `python3 scripts/dependency_egress_audit.py` | **clean** (no egress-capable runtime imports) |

## trufflehog findings (unverified, all intentional)

| File | Detector | Why it is not a leak |
|---|---|---|
| `packages/python-sdk/src/agentwatch/selftest.py` | Postgres | `postgres://admin:pgLEAK@db:5432/app` — the redaction self-test fixture |
| `packages/python-sdk/tests/test_secrets.py` (×2) | Postgres | `postgres://user:pass@host:5432/app` — redaction unit fixture |
| `packages/python-sdk/tests/test_config_explain.py` | Postgres | the same placeholder in a config-explain fixture |
| `docs/plans/m4-store-redaction-execution-plan.md` | Postgres | RFC-style placeholder in a design note |

`gitleaks` reports **no leaks**; the synthetic `sk-abcdefgh1234` fixtures and the field-test/console tokens are
allowlisted by path. Dependency and egress checks are clean.

## Reproduction

```bash
make security-scan          # writes docs/release/v0.2.0/security-scan/
```
