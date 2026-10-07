# OWASP Agentic coverage map (ASI 2026 + AST10) — executable evidence

**BLUF:** `agentwatch compliance report --framework owasp-asi-2026` renders one row per OWASP Top 10 for
Agentic Applications 2026 risk (ASI01–ASI10) and a section for the Agentic Skills Top 10 (AST01–AST10). Each row
states **what the record evidences**, the **command that regenerates it** (or `not evidenced`), **what it cannot
evidence**, and a **fidelity tier**. It cites regenerable evidence or says plainly that the record cannot
evidence the risk — it never certifies and never claims prevention.

**Status:** published (2026-10-06, v0.2.0-expanded) · **Milestone:** M29 (ASI-1) ·
Sources: [PRD 59](../prd/59-owasp-agentic-and-standards-coverage.md),
[design/owasp-asi-mapping.md](../design/owasp-asi-mapping.md), [reference/compliance.md](../reference/compliance.md).

## Not a certification

This report is **evidence of recorded activity and configuration for this installation**. It is not a
certification, not an audit opinion, and not a statement that any ASI/AST risk has been prevented or mitigated.
A row marked **evidenced** or **signal** names a command that regenerates a record; a row marked **not evidenced**
means agentwatch does not yet capture that surface (the owning dependency is named).

## Rows

| Risk | What the record evidences | Command | Cannot evidence | Tier |
|---|---|---|---|---|
| ASI01 Goal Hijack | content→argument flow edges + injection-shape observations | `flow` | intent; does not block | signal |
| ASI02 Tool Misuse & Exploitation | every tool call + change footprint | `impact` | misuse classification; policy enforcement | evidenced |
| ASI03 Identity & Privilege Abuse | identity + delegation (IDN) | `search --identity` | privilege/authorization correctness (needs APV-3) | signal |
| ASI04 Agentic Supply Chain | not evidenced (needs 30.CAP-1 inventory) | not evidenced | skill/plugin/hook/rules provenance & drift | not evidenced |
| ASI05 Unexpected Code Execution | command classes + change footprint | `impact` | sandbox enforcement / a block | signal |
| ASI06 Memory & Context Poisoning | memory read/write/delete records (DET-7) | `search --memory` | poisoning determination; attribution | signal |
| ASI07 Insecure Inter-Agent Comms | not evidenced (needs 29.A2A-1/2 + trace) | not evidenced | A2A/delegation message capture | not evidenced |
| ASI08 Cascading Agent Failures | subagent fan-out + retry/cascade observations | `tree` | root cause / severity | signal |
| ASI09 Human-Agent Trust Exploitation | not evidenced (needs 29.APV-3 oversight) | not evidenced | approval mix, bypass, latency | not evidenced |
| ASI10 Rogue Agents | behavior-fingerprint grouping | `sessions --group-by-behavior` | a "rogue" label | signal |
| AST01–AST10 (Agentic Skills Top 10) | not evidenced (needs 30.CAP-1/2 + 30.SBX-1) | not evidenced | skill inventory, drift, metadata, isolation | not evidenced |

## Executable evidence (runs in CI)

Seed the reproducible dataset, then regenerate the report:

```sh run
export DEMO_STORE="${DEMO_STORE:-/tmp/agentwatch-demo}"
python3 scripts/seed-investigations.py --store "$DEMO_STORE"
agentwatch --set store.path="$DEMO_STORE" compliance report --framework owasp-asi-2026
```

The ASI rows that cite a command — each command is run here so the map cannot drift:

```sh run
agentwatch --set store.path="$DEMO_STORE" flow sess-secret
agentwatch --set store.path="$DEMO_STORE" impact sess-loop
agentwatch --set store.path="$DEMO_STORE" search --identity demo-agent
agentwatch --set store.path="$DEMO_STORE" impact sess-denied
agentwatch --set store.path="$DEMO_STORE" search --memory
agentwatch --set store.path="$DEMO_STORE" tree sess-loop
agentwatch --set store.path="$DEMO_STORE" sessions --group-by-behavior
```

The `not evidenced` rows (ASI04, ASI07, ASI09, AST01–AST10) carry **no** command: the surface is not captured on
this branch and the owning ticket is named in the row. That is the honest answer, not fake evidence.
