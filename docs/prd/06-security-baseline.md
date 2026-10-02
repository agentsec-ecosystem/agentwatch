# PRD 06 — Security Baseline

**BLUF:** agentwatch is in the security path, so it must be safe by default: no secrets on disk, no data
exfiltration, and fail-closed behavior when its own configuration is tampered with.

## Baseline

- **Redaction by default** — no secrets/PII in stored arguments (R7); verified by an attack pack.
- **Local-first** — no network egress unless the operator configures export (R6).
- **Tamper-evident records** — hash-chaining of stored records (R11).
- **Fail-closed on tamper** — edits to hook config or policy files are detected and alerted (ecosystem threat model).
- **Signed releases + provenance** — artifact signing and SHA-pinned upgrades (ecosystem supply-chain policy).
- **Vulnerability disclosure** — see the org [SECURITY policy](https://github.com/agentsec-ecosystem/.github/blob/main/SECURITY.md).

## Threats to consider

Hook config edit · record store tampering · accidental secret capture in arguments · silent recording
failure (fail-open). Each needs an explicit test in the v0.1.0 field test.
