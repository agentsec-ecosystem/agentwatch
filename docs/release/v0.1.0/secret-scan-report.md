# Secret Scan Report — v0.1.0 (M24 24.3 / 24.5)

**BLUF:** agentwatch's own source (code, docs, scripts, workflows, git history) contains
**0 real secrets**. Two independent scanners (gitleaks, trufflehog) agree; the only trufflehog
hits are deliberate redaction fixtures and RFC-style placeholder connection strings, listed
below. Dependency scan (`pip-audit`) reports **0 known vulnerabilities**. Reproduce with
`make security-scan`. Third-party ported example code and committed field-test evidence are
scoped out by an explicit, reviewed allowlist — not hidden.

## Scope

- **In scope:** first-party source — `packages/`, `services/`, `apps/`, `scripts/`, `docs/`,
  `.github/`, and the full git history of the repository.
- **Out of scope (allowlisted, with reason):**
  - `m13-agents/**` — ported predecessor example agents (third-party; not agentwatch source).
  - Intentional secret material used to test redaction and the self-test:
    `packages/python-sdk/src/agentwatch/selftest.py` (`MIIEowSECRETMATERIAL`),
    `packages/python-sdk/tests/test_secrets.py`,
    `packages/python-sdk/tests/test_redaction_properties.py`,
    `packages/python-sdk/tests/_secret_oracle.py`,
    `packages/python-sdk/tests/fixtures/ingest/otel_trace.json` (`sk-abcdefgh1234`).
    These fixtures **must exist** — they prove the redactor catches real token shapes.
  - `field-test/v0.1.0/results/**` — committed field-test evidence: ephemeral per-run keys
    (`flow.key`, `signing.key`) and decrypted stores that intentionally contain test secrets.

The allowlist is committed as [`.gitleaks.toml`](../../../.gitleaks.toml); the trufflehog
path excludes are committed as
[`scripts/security/trufflehog-exclude.txt`](../../../scripts/security/trufflehog-exclude.txt).

## Tools & commands

Run everything with `make security-scan` (or `bash scripts/security_scan.sh`). Evidence is
written to [`security-scan/`](security-scan/).

| Tool | Version | Command |
|---|---|---|
| gitleaks | 8.30.1 | `gitleaks detect --config .gitleaks.toml` (git history) |
| trufflehog | 3.97.4 | `trufflehog filesystem packages services apps scripts docs .github --no-update --no-verification --json -x scripts/security/trufflehog-exclude.txt` |
| pip-audit | 2.10.1 | `pip-audit <package> --format json` for each of `packages/python-sdk`, `services/api`, `services/analytics` |
| egress audit | — | `python3 scripts/dependency_egress_audit.py` |

> **Tooling gotcha:** a pip-installed trufflehog **v2** may shadow the Homebrew **v3** binary
> on `PATH`. v2 has no `filesystem` subcommand and both accept `filesystem --help`, so
> `scripts/security_scan.sh` detects v3 by a flag only it exposes and prefers the Homebrew
> binary. Use v3 — v2 does not scan the working tree as documented here.

## Results

| Scan | Scope | Findings |
|---|---|---|
| gitleaks | git history (221 commits, ~45 MB), first-party | **0 leaks** |
| trufflehog | working tree, first-party paths (caches/node_modules/field-test excluded) | **5 unverified** — all intentional placeholders (below) |
| pip-audit | `python-sdk` (4 deps), `api` (27 deps), `analytics` (28 deps) | **0 known vulnerabilities** |
| egress audit | runtime imports across packages/services | **0 egress-capable imports** |

**0 real secrets in first-party source or history; 0 known dependency vulnerabilities.**

### trufflehog unverified hits (all intentional)

Every hit is a documentation placeholder or a redaction fixture that **must exist** to prove
the redactor catches credential shapes. trufflehog cannot verify them (they are not live
credentials), so they are reported as unverified rather than hidden by an allowlist.

| File:line | Detector | Why it is expected |
|---|---|---|
| `packages/python-sdk/src/agentwatch/selftest.py:21` | Postgres | Redaction self-test fixture (fake `pgLEAK` password) |
| `packages/python-sdk/tests/test_secrets.py:93,108` | Postgres | Redaction test fixture (fake `user:pass` URI) |
| `packages/python-sdk/tests/test_config_explain.py:66` | Postgres | Config-redaction test fixture (fake `pgLEAK` password) |
| `docs/plans/m4-store-redaction-execution-plan.md:71` | Postgres | RFC-style placeholder URI in a plan doc |

Literal match values are intentionally **not** reproduced here; the machine-readable
evidence (which does contain them, and is excluded from the scan as generated output)
is under [`security-scan/`](security-scan/).

## Notes

- Before this scan, gitleaks (no config, whole repo) flagged 5 items: 2 in `m13-agents/**/.env.example`
  (key-prefix placeholders — third-party, now untracked) and 3 intentional test/self-test fixtures.
  With the reviewed allowlist, first-party scope is clean.
- The `m13-agents` `.env.example` (with `sk-ant-api03...` / `sk-proj-...` / `lsv2_sk_...`
  placeholders) remains in **git history** though it is no longer in the tree. A history rewrite
  (`git filter-repo` + force-push) was **not** performed, by decision, because the values are
  truncated placeholders (not usable keys) and rewriting a shared branch is disruptive. This is a
  stated residual, not a hidden gap.
- GitHub org-level secret scanning + push protection are also enabled for the repository.
- Raw, machine-readable evidence for this run is committed under
  [`security-scan/`](security-scan/): `gitleaks.json`, `trufflehog.jsonl`, and one
  `pip-audit-*.json` per package. `make security-scan` regenerates them and exits non-zero on a
  real first-party secret leak or a dependency vulnerability.
