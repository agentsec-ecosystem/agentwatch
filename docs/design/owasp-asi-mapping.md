# Design — OWASP Agentic (ASI) Coverage Mapping

**BLUF:** The mapping behind `compliance report --framework owasp-asi-2026`: for each OWASP Top-10 for Agentic
Applications 2026 risk (ASI01–ASI10) and the Agentic Skills Top 10 (AST01–AST10), what the record **evidences**,
the command that regenerates it, what it **cannot** evidence, and the fidelity tier. Cites or says "not
evidenced" — never certifies.

**Status:** published (2026-10-06, v0.2.0-expanded) · **Milestone:** M29 (ASI-1) · Sources:
[PRD 59](../prd/59-owasp-agentic-and-standards-coverage.md), [../compliance/standard-artifacts.md](../compliance/standard-artifacts.md),
[../compliance/owasp-asi-2026.md](../compliance/owasp-asi-2026.md) (executable rows), PRD 39 (W1 discipline).

## Rows

Each row is `what the record evidences → regenerating command → what it cannot evidence → tier`. A row whose
evidence needs a ticket not yet landed on the `m29/standards` branch says **not evidenced** and names the owning
dependency — the honest answer, not fabricated evidence. Tiers: **evidenced** (the record carries the fact),
**signal** (an observation for review, not a determination), **not evidenced** (no capture yet).

| Risk | What agentwatch evidences (or "not evidenced") | Command | Cannot evidence | Tier |
|---|---|---|---|---|
| ASI01 Goal Hijack | content-flow edges (S22) + DET-6 injection **signals** | `flow` | intent; not an enforcement verdict | signal |
| ASI02 Tool Misuse | full tool-call record + `impact` footprint | `impact` | misuse classification; policy enforcement | evidenced |
| ASI03 Identity & Privilege Abuse | `agent_identity` + delegation (IDN) + authorization (APV) | `search --identity`; `oversight` (29.APV-3) | privilege/authorization correctness | signal |
| ASI04 Supply Chain | capability inventory + drift (CAP) | not evidenced (30.CAP-1) | skill/plugin/hook provenance & drift | not evidenced |
| ASI05 Unexpected Code Execution | `impact` command classes (cls1) + sandbox events (SBX) | `impact` | sandbox enforcement; not a block | signal |
| ASI06 Memory Poisoning | memory as capability (MEM) + DET-7 memory observations | `search --memory` | poisoning determination; attribution | signal |
| ASI07 Insecure Inter-Agent Comms | A2A/Trace correlation + delegation records | not evidenced (29.A2A-1/2) | A2A/delegation message capture | not evidenced |
| ASI08 Cascading Failures | subagent tree + retry/cascade detectors | `tree` | root cause / severity | signal |
| ASI09 Human-Agent Trust Exploitation | `oversight` (approval mix, bypass, latency) | not evidenced (29.APV-3) | approval mix, bypass, latency | not evidenced |
| ASI10 Rogue Agents | behavior-fingerprint grouping + drift (as signals) | `sessions --group-by-behavior` | a "rogue" label | signal |

## Agentic Skills Top 10 (AST10)

The AST10 section maps the OWASP Agentic Skills Top 10 (v1.0-2026) to CAP/MEM evidence. On this branch the
capability inventory is M30 (30.CAP-1/2) and the sandbox-boundary events are 30.SBX-1, so every AST row is
**not evidenced** with the dependency named; no command is claimed and none is faked.

| Risk | What agentwatch evidences (or "not evidenced") | Command |
|---|---|---|
| AST01 Malicious Skills | not evidenced — needs 30.CAP-1 | not evidenced |
| AST02 Supply Chain Compromise | not evidenced — needs 30.CAP-1/30.CAP-2 | not evidenced |
| AST03 Over-Privileged Skills | not evidenced — needs 30.CAP-1 | not evidenced |
| AST04 Insecure Metadata | not evidenced — needs 30.CAP-1 | not evidenced |
| AST05 Untrusted External Instructions | not evidenced — needs 30.CAP-1 + DET-6 | not evidenced |
| AST06 Weak Isolation | not evidenced — needs 30.SBX-1 | not evidenced |
| AST07 Update Drift | not evidenced — needs 30.CAP-2 | not evidenced |
| AST08 Poor Scanning | not evidenced — agentwatch is not a skill scanner | not evidenced |
| AST09 No Governance & Shadow AI | not evidenced — needs 30.CAP-1 + 29.ACC | not evidenced |
| AST10 Cross-Platform Reuse | not evidenced — needs 30.CAP-1 | not evidenced |

## Rules

- Every row has an evidence command **or** an explicit "not evidenced"; a row never claims prevention.
- The non-certification statement is included in the report.
- Fidelity tier per row; "signal" is not a determination and "evidenced" is not a mitigation claim.
- Every evidenced row's command runs in the executable-docs gate
  ([../compliance/owasp-asi-2026.md](../compliance/owasp-asi-2026.md), covered by `check_docs_commands.py`).

## Testing

- All ten ASI rows present, each with evidence-or-"not evidenced", cannot-evidence, and a tier; the AST10 section
  is present (FT-ASI-1).
- No prevention/certification language in any row (assertion); the non-certification statement is present.
- Every evidenced row's command runs in the executable-docs gate.

## Decision

**D-59.x — row evidence map:** rows cite a regenerating command that runs in CI, or say "not evidenced" and name
the owning dependency (29.APV-3, 29.A2A-1/2, 30.CAP-1/2, 30.SBX-1). The map never claims prevention or
certification; carried in the report template (`agentwatch.compliance._ASI_ROWS`).
