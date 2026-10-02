# Testing & Parity Verification Strategy

**BLUF:** How agentwatch proves it works — and how it proves **shipped-feature parity** — in CI.

Status: **draft** (v0.1.0).

## Layers

1. **Unit** — normalizers, redaction, hash chain, schema validation.
2. **Contract** — read API shapes (`/runs`, `/fleet`, `/compare`, `/anomalies`); SDK surface.
3. **Integration** — hooks → daemon → store → export on Claude Code.
4. **E2E (UI)** — Playwright across the five views.
5. **Field test** — real sessions; fresh-machine ≤15 min; attack pack for secrets.
6. **Parity suite** — for each PRD 10 matrix-A row, an automated test that fails if the capability regresses.

## Gates

- ruff zero, mypy strict, tests green, coverage **≥95%** (NFR-11).
- **Parity gate:** v1.0 requires every matrix-A row green.
- **Security gate:** redaction attack pack zero leaks; export blocked until it passes.

## Evidence

CI badges + release security audit + field-test report per release.
