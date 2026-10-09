# agentwatch v0.2.0 — Release Notes

Status: **release-ready** — see the [release checklist & go/no-go](release-checklist.md). Tagging/publishing
happen at M32 (32.21/32.22).

## Highlights

- **Read-only console (`agentwatch ui`)** — loopback-only, token-gated HTTP console over the chain store with
  **no Docker**; UI numbers equal the CLI `--json` (ADR-0036).
- **Investigation skill + versioned CLI JSON** — `sessions`/`search`/`replay`/`impact`/`blame` are a versioned
  contract (`schema/cli/v0.1.0/`) with a shipped skill (`docs/skills/investigation/SKILL.md`); a scripted agent
  reaches the documented answers on the demo store.
- **Capability & memory supply chain** — plugins and memory stores inventoried with content digests; the
  **Plugin4Shell** class ("content changed, version unchanged") is detected; out-of-band memory edits are
  flagged and attributed (or marked unattributable).
- **Provenance** — `agentwatch provenance <commit|file|pr>` resolves a commit to the contributing session
  (<2 s); Cursor **Agent Trace** export validates; commit→session is honest about "no recorded agent activity".
- **Approval provenance v2** — no auto/bypass call is reported as `user`; `oversight` reports the authorization
  mix, sessions by mode, and the bypass interval.
- **Sandbox boundary** — `oversight` reports the % of calls unsandboxed and denials by class.
- **Legal hold** — held records survive retention, purge, and index rebuild (CUJ-32).
- **Compliance** — OWASP **ASI-2026 + AST10** report; ISO 42001/27001, SOC 2, NIST 800-92, EU AI Act Art.12
  templates — all offline with per-row evidence commands.
- **Native telemetry & ingest** — Claude Code native OTel joins hook records by `tool_use_id`; gateway records
  carry exact-vs-estimated cost; **Cursor native hooks** adapter; **system-effects ingest** (opt-in,
  `source: system-ingest`).
- **Two OTel backends** — agent-span trees proven in **Jaeger and Tempo**.
- **Harness breadth** — Claude Code (full), Cursor (native hooks, `fixture-verified`), plus provisional modeled
  Codex CLI / Gemini CLI / CrewAI / PydanticAI ([compatibility matrix](../../reference/compatibility.md)).

## Install

```sh
pip install agentsec-agentwatch==0.2.0    # Python CLI + SDK
npx @agentsec-ecosystem/cli init           # install hooks + local daemon (monitor-only)
```

## Field test

The v0.2.0 field test executed **all 94 cases**: **92 PASS · 0 FAIL · 1 not run (declared, FT-XHT-2) ·
1 N/A (FT-WIN-1, Windows unsupported)**; 90/92 grounded. See the
[field-test report](../../field-test/v0.2.0/FIELD_TEST_REPORT.md).

## Verification at the release commit

- SDK/API/analytics: full suite green at ≥95% coverage (95.26 / 95.75 / 96.28); `ruff` zero; `mypy --strict`
  clean; repo guard green.
- Security: [security-audit.md](security-audit.md) (0 unresolved) + [secret-scan-report.md](secret-scan-report.md)
  (gitleaks/trufflehog/pip-audit/egress; `make security-scan`).
- Supply chain: [release-evidence.md](release-evidence.md) — `make release-dry-run` builds and verifies the
  bundle (CycloneDX SBOM + checksums + `verify-release`); CI signs (cosign) and attests provenance on the tag.
- Dependencies/licences: [dependency-review.md](dependency-review.md); notices: `THIRD_PARTY_NOTICES.md`.
- Compliance: [compliance-matrix.md](compliance-matrix.md); OpenSSF: `docs/reference/open-source-checklist.md`.
- Versioning: one version across SDK/CLI/CHANGELOG, enforced by `tests/test_release_tooling.py`.
- First run: [first-run-evidence.md](first-run-evidence.md).
- Release gate: [release-checklist.md](release-checklist.md) (PRD 40 §5 gates 1–16; gate 9 partial — Windows
  unsupported).

## Release actions (M32 — not before)

- [ ] **32.20** cut the release branch + merge `feat-v0.2.0` → `main`.
- [ ] **32.21** tag `v0.2.0` (triggers `release.yml`: build + SBOM + checksums + Sigstore + GitHub release).
- [ ] **32.22** publish to PyPI + npm (trusted publishing).
- [ ] **32.23** post-release fresh-install verification.
