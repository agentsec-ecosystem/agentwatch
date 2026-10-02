# PRD 06 — Security Baseline

**BLUF:** agentwatch sits in the security path, so it must be safe by default: no secrets on disk, no
exfiltration, and fail-closed when its own configuration is tampered with. Its records are the evidence
other tools and auditors rely on, so their integrity is a first-class requirement.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## Assets to protect

| Asset | Why it matters |
|---|---|
| Recorded tool-call arguments | May contain secrets, PII, or sensitive file contents |
| The record store | Forensic/compliance evidence; tampering destroys trust |
| Hook / daemon configuration | If silently disabled, recording stops (fail-open is the worst outcome) |
| The security-event stream | Consumed by policy/replay/compliance tools |

## Baseline controls (v0.1.0)

- **Redaction by default** (R7) — arguments are redacted at normalization time, **before** persistence
  (`DD-06`). No secret/PII is ever written to disk.
- **Local-first** (R6) — no network egress unless the operator configures OTLP export (`DD-03`).
- **Tamper-evident store** — append-only, hash-chained records (`DD-07`, R11). Any modification breaks the
  chain.
- **Fail-closed on tamper** — edits to hook config or policy files are detected and must fail closed, not
  silently stop recording (ecosystem threat model).
- **Signed releases + provenance** — artifact signing and SHA-pinned upgrades, per the org supply-chain
  policy.
- **Least privilege** — the daemon runs with the minimum local permissions needed to receive hook events and
  write its store.

## Threat scenarios (must have explicit tests)

1. **Hook-config edit** — an attacker disables recording → detected, alerted, fail-closed.
2. **Store tampering** — a record is modified or removed → hash chain breaks.
3. **Accidental secret capture** — a tool argument contains a credential → redacted before storage.
4. **Silent recording failure** — the daemon dies → surfaced, not silent (fail-open prevention).
5. **Exfiltration via export** — export is opt-in and explicit; no hidden endpoints.

## Privacy

Records are local by default. When export is configured, the operator chooses the destination; documented
guidance will cover redaction verification before enabling export.

## Disclosure

Report vulnerabilities per the organization
[SECURITY policy](https://github.com/agentsec-ecosystem/.github/blob/main/SECURITY.md) — private advisory,
never a public issue.

## Decisions

- **Hash chain (C2 / DD-08):** detect-only in v0.1.0 (no key).
- **Export gating (C4 / DD-09):** OTLP export is blocked until a redaction self-test passes.
