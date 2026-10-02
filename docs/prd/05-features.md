# PRD 05 — Features

**BLUF:** v0.1.0 (P0, R1–R8) records every Claude Code tool call, redacted by default, exported as OTel
GenAI, with the security-event schema published and session replay. Later requirements extend harnesses
and inventory.

## P0 — Must have (v0.1.0)

| # | Requirement | Acceptance criterion |
|---|---|---|
| R1 | Record every tool call (name, redacted args by default, outcome, agent identity, session) | A Claude Code session's action timeline is reconstructable |
| R2 | Zero code changes to the harness to start recording | Fresh machine → first recorded call ≤15 min |
| R3 | Top-3 harnesses at launch (Claude Code, Cursor, Codex CLI) | Native surface met; documented gaps published |
| R4 | Export standard OTel GenAI format | Loads into ≥2 common backends unmodified |
| R5 | Define + emit the open security-event schema (`denied`, `policy-fired`, `secret-detected`, `revoked`, `halted`) | Schema published; emitted by ≥1 other ecosystem tool |
| R6 | Local-first storage | No network required for core function |
| R7 | Redaction-by-default | Attack pack finds zero secrets in stored records |
| R8 | Session replay | Replay matches raw transcript in an automated test |

## P1 — Should have (v0.1.x)

- R9 shadow-agent/MCP-server inventory (local scope) · R10 Gemini CLI + generic MCP clients + adapter API ·
  R11 retention controls + tamper-evident hash-chaining.

## P2 — Nice to have

- R12 browser-based local replay viewer (read-only) · R13 fleet aggregation (opt-in, self-hosted).

## Non-requirements

No alerting. No injection/behavioral/intent analysis of any kind. No cloud service in v1; not a SIEM.
