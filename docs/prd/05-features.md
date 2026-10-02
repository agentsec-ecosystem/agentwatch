# PRD 05 — What (Features)

**BLUF:** v0.1.0 records every Claude Code tool call, redacted by default, in OpenTelemetry GenAI format,
stored locally, replayable, with the security-event schema defined and published. Everything else is
explicitly out of scope.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## v0.1.0 scope

One harness (**Claude Code**), monitor-only by default, zero agent-side code changes, ≤15-minute setup.

## P0 — Must have (v0.1.0)

| # | Requirement | Acceptance criterion |
|---|---|---|
| **R1** | Record every tool call — tool name, arguments **redacted by default**, outcome, agent identity, session | A Claude Code session's full action timeline is reconstructable from the record |
| **R2** | Zero code changes to the agent/harness to start recording | Fresh machine → first recorded tool call in ≤15 min for Claude Code |
| **R3** | Harness coverage — Claude Code at v0.1.0 | Native Pre/PostToolUse surface met; unsupported classes documented honestly |
| **R4** | Export the standard open telemetry format for GenAI/agent traces | Data loads into at least two common backends unmodified |
| **R5** | Define **and emit** the open security-event schema (`denied`, `policy-fired`, `secret-detected`, `revoked`, `halted`) | Schema published; events emitted by ≥1 other ecosystem tool |
| **R6** | Local-first storage; data leaves the machine only if export is configured | No network required for core function |
| **R7** | Redaction-by-default — no secrets/PII in stored arguments | Verification attack pack finds zero leaks in stored records |
| **R8** | Session replay — given a session id, produce the ordered action timeline | Replay matches the raw transcript in an automated test |

## P1 — Should have (v0.1.x)

- **R9** Shadow-agent / MCP-server inventory for the machine (local scope only — fleet discovery is
  commercial territory).
- **R10** Gemini CLI + generic MCP-client support; adapter API for community harnesses **and** ≥3 Tier-2
  framework adapters (LangGraph, CrewAI, PydanticAI prioritized).
- **R11** Retention controls (size/time caps) + tamper-evident hash-chaining of stored records.

## P2 — Nice to have

- **R12** Browser-based local replay viewer (read-only; we ship data, not a dashboard).
- **R13** Fleet aggregation mode (opt-in, self-hosted).

## Feature parity with superseded projects (required)

agentwatch supersedes **agent-exec-trace / AgentObservatory (#102)** and **AgentWatch (#66)**. No feature
from either is silently dropped: every capability is delivered by agentwatch, delivered by a named sibling
tool, or explicitly waived with rationale — tracked in [PRD 10](10-feature-parity.md). Parity adds to the
roadmap:

- **v0.2.0** — step-level telemetry (step type reason/act/observe/verify, tokens, confidence); behavior
  event classes (memory, validation, approval, escalation); deployment correlation; retention +
  hash-chaining.
- **v0.3.0** — analytics/query surface (cost-per-success, tool overuse, version comparison); drift
  **signals** exposed as events (detection/alerting delegated to agentpolicy + agentinbox); framework
  adapters.
- **v1.x** — local replay/explorer viewer (R12); fleet aggregation (R13); multi-agent interaction maps.

Two parity decisions need sign-off — delegated drift/alerting, and the fleet-dashboard waiver. See
[PRD 10 §C](10-feature-parity.md).

## Explicit non-requirements

- No alerting (that's agentpolicy's decisions on these events) — agentwatch only records + exposes.
- No injection / behavioral / intent analysis of any kind.
- No cloud service in v1; not a SIEM.
- No evaluation framework in this repo.

## Harness compatibility (required)

Per the [ecosystem matrix](https://github.com/agentsec-ecosystem/.github/blob/main/ROADMAP.md), agentwatch is
OTel-native (any harness) plus named adapters.

| Version | Tier-1 coding agents | Tier-2 frameworks |
|---|---|---|
| **v0.1.0** | **Claude Code** | — |
| v0.1.x / v0.2.0 | + Cursor (proxy-interposition where hooks are insufficient) | — |
| v0.3.0 | + Codex CLI, Gemini CLI; Copilot via OTel/lower layer | LangGraph, CrewAI, PydanticAI (≥3) |

> **Documented tension:** the ecosystem threshold asks for **≥2 Tier-1 at v0.1.0**, while the meta-MVP
> keeps v0.1.0 to **Claude Code only**. Resolution: v0.1.0 ships Claude Code; Cursor lands in v0.1.x without
> moving the v0.1.0 release gate. Tracked as an open decision.

## Open questions

- Cursor full-fidelity recording — native hooks vs proxy interposition for which event classes?
- Schema stewardship: solo steward vs proposing into OTel GenAI from day one (`DD-05`)?
