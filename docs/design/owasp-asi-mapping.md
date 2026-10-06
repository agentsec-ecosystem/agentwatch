# Design — OWASP Agentic (ASI) Coverage Mapping

**BLUF:** The mapping behind `compliance report --framework owasp-asi-2026`: for each OWASP Top-10 for Agentic
Applications 2026 risk (ASI01–ASI10) and the Agentic Skills Top 10, what the record **evidences**, the command that
regenerates it, what it **cannot** evidence, and the fidelity tier. Cites or says "not evidenced" — never certifies.

**Status:** proposed (2026-10-05, v0.2.0-expanded) · **Milestone:** M27 · Sources:
[PRD 59](../prd/59-owasp-agentic-and-standards-coverage.md), [../compliance/standard-artifacts.md](../compliance/standard-artifacts.md),
PRD 39 (W1 discipline).

## Rows (draft)

| Risk | What agentwatch evidences (or "not evidenced") | Command |
|---|---|---|
| ASI01 Goal Hijack | content-flow edges (S22) + DET-6 injection **signals**; not an enforcement verdict | `flow`, `search --anomaly` |
| ASI02 Tool Misuse | full tool-call record + `impact` footprint | `impact` |
| ASI03 Identity & Privilege Abuse | `agent_identity` + delegation (IDN) + authorization (APV) | `search --identity`, `oversight` |
| ASI04 Supply Chain | capability inventory + drift (CAP) | `inventory --capabilities --diff` |
| ASI05 Unexpected Code Execution | `impact` command classes (cls1) + sandbox events (SBX); not a block | `impact`, `oversight` |
| ASI06 Memory Poisoning | memory as capability (MEM) + DET-7 memory observations | `inventory`, `search --memory` |
| ASI07 Insecure Inter-Agent Comms | A2A/Trace correlation + delegation records | `trace` |
| ASI08 Cascading Failures | subagent tree + retry/cascade detectors | `tree`, `search --anomaly` |
| ASI09 Human-Agent Trust Exploitation | `oversight` (approval mix, bypass, latency) | `oversight` |
| ASI10 Rogue Agents | detectors + drift + behavior fingerprint (as signals) | `search --group-by-behavior` |

Agentic Skills Top 10: a section mapping skill risks to CAP/MEM evidence.

## Rules

- Every row has an evidence command (executable-docs gate) **or** an explicit "not evidenced".
- Nothing claims prevention; the non-certification statement (W1) is included.
- Fidelity tier per row where relevant.

## Testing

- All ten rows present; every command runs in CI (FT-ASI-1).
- No prevention/certification language (assertion).

## Decision

D-59.x — row evidence map; carried in the report template.
