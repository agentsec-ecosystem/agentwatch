# PRD 18 — Security & Compliance Controls

**BLUF:** agentwatch maps to recognized security and compliance frameworks — both for the product's own
posture and as the evidence source other tools (agentcomply) draw on. Coverage is explicit, published, and
testable; we don't claim what we can't prove.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

Sources: ecosystem research
`04-standards-and-architecture/01-standards-compliance-certifications.md` and the org
[SECURITY policy](https://github.com/agentsec-ecosystem/.github/blob/main/SECURITY.md).

## A. Product's own security posture (what we implement)

| Control | Standard ref | How agentwatch satisfies it | Test |
|---|---|---|---|
| No secrets at rest | OWASP LLM02 (sensitive info disclosure) | Redaction-by-default before storage (DD-06, R7); 4 privacy modes | Redaction attack pack: 0 leaks in store |
| Tamper-evident records | NIST SSDF (audit integrity); SOC 2 CC7 | Hash-chained append-only store (DD-07) | `verify-store` chain test; F4 fault test |
| Fail-closed, never silent | NIST SSDF; SOC 2 CC7 | Tamper/failure surfaces, not silent stop (NFR-8, [PRD 17](17-error-handling.md)) | F1–F10 injected-fault tests |
| Local-first, opt-in egress | OWASP LLM02; privacy by default | No network by default; export gated on redaction self-test (DD-09) | Export-locked-until-self-test test |
| Supply-chain integrity | OpenSSF Scorecard; SLSA | Signed releases + SBOM + provenance; pinned deps; DCO; Scorecard workflow | Scorecard grade recorded per release |
| Vulnerability disclosure | CVE program norm | Org SECURITY policy; private advisories | security.txt + advisory flow |
| Least-privilege daemon | OWASP ASVS | Minimal local perms; no secret material in config | Config validation test |
| Self-health visible | SOC 2 CC1/CC7 | `/healthz` + `agentwatch status` (PRD 13) | Health endpoint contract test |

## B. Framework coverage matrix (what we publish)

We publish a control→risk mapping; coverage is honest, including "not covered by agentwatch (covered by
sibling X)".

| Framework | agentwatch coverage | Notes |
|---|---|---|
| **OWASP Top 10 for LLM Applications 2025** | LLM02 (sensitive-info disclosure: redaction + local-first); LLM05 (improper output handling: redaction modes); partial LLM06 (excessive agency: *records* tool calls — enforcement is agentpolicy) | Coverage matrix published per release |
| **OWASP Agentic AI Top-10** (draft) | Tracked; identity-confusion and excessive-agency *signals* recorded; enforcement delegated | Be first with a mapping when finalized |
| **MITRE ATLAS** | Detector rules tagged to ATLAS techniques; incident register feeds ATLAS-style mappings | Mapping table in docs |
| **NIST AI RMF + GenAI Profile (AI 600-1)** | "Manage" function: records + audit trail + evidence export | Controls-mapping appendix |
| **NIST SSDF (SP 800-218)** | Our own secure dev: DCO, branch rulesets, signed releases, SBOM, Scorecard | OpenSSF checklist maps this |
| **ISO/IEC 42001** (AI management) | Controls-mapping appendix for enterprise buyers | Appendix; not certified in v1 |
| **SOC 2** | Type I/II evidence source — agentwatch's own audit log *is* the evidence pipeline | Type I target post-traction (Wave 3, agentcomply) |

## C. What agentwatch explicitly does NOT claim

- **Not a certified product (v1).** SOC 2 Type I/II, ISO 27001 are post-traction (Wave 3) — we say so.
- **Not an injection / intent classifier.** OWASP LLM01 (prompt injection) mitigation is via isolation and
  enforcement (agentpolicy/agentseatbelt), not detection claims. We record; we don't claim to detect
  injection as a security boundary.
- **No ML in the enforcement path.** The LLM-augmented detectors are observability *signals*, not controls.
- **No FIPS/Common Criteria** in v1 (we use OS-native crypto; FIPS-mode is a platform claim, not our cert).

## D. OpenSSF / supply-chain (the "Plugin4Shell lesson applied to ourselves")

Per org governance + `docs/reference/open-source-checklist.md`:

- OpenSSF Scorecard workflow on every repo; **target grade A**.
- Signed releases (Sigstore) + SBOM + provenance (SLSA); pinned deps; Dependabot + secret scanning.
- DCO on every commit; branch ruleset (PR required); CODEOWNERS.
- Fuzzed parsers (MCP JSON-RPC, record schema) — target OSS-Fuzz integration before v1.0.

## E. Reliability mechanisms (inherent, beyond certs)

From the research reliability scorecard:

- **Fail-closed is explicit and configurable** — default fail-closed for the recorder; recording gaps surface,
  never silent.
- **Policy determinism** — not applicable to agentwatch (no policy); relevant to agentpolicy.
- **Audit-log integrity** — append-only, hash-chained, OTel-exportable (our logs are forensic evidence).
- **Self-testing** — redaction attack pack + fault-injection suite run in CI.

## F. Release-gate evidence

Before each release, publish:

- [ ] OWASP LLM Top-10 coverage matrix (control → risk → test).
- [ ] OpenSSF Scorecard grade recorded; supply-chain checklist green.
- [ ] Security audit (per-version) — `docs/release/vX/security-audit.md`.
- [ ] Redaction attack pack: 0 leaks.
- [ ] SBOM + signed artifacts.

## G. Open questions

- **SOC 2 evidence window:** start the evidence pipeline from v0.1.0 (audit log of our own product +
  change-management records) so a Type II 6–12-month window can begin — confirm we start collecting from
  v0.1.0 even though certification is post-traction.
- **OWASP Agentic AI mapping timing:** publish within a week of finalization (the ecosystem success
  criterion) — track the standard's status.
