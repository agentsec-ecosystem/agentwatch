# Demo & Seed Data — agentwatch

**BLUF:** A one-command demo (parity with the shipped project's demo agent + seed script) for the README
and the three ecosystem demos.

Status: **draft** (v0.1.0 ships a recording demo; full seed comes with analytics in v0.2.0).

## v0.1.0 demo

```sh
agentwatch init
# run a sample Claude Code session (or the demo script)
agentwatch sessions
agentwatch replay <id>
```

## Seed data (v0.2.0+, parity with the shipped 96-run seed)

- A demo agent (LangGraph `request-triage`) with deterministic paths: normal, loop, high-cost.
- `make seed-e2e` produces 96 mock runs, ~240 anomalies, 4 agents.
- Used by E2E tests and the operator UI.

## Three ecosystem demos (Wave 0 gate)

1. Replit gate (destructive command → `ask`)
2. Poisoned-tool block (allowlist + taint)
3. Kill-switch (one command, all credentials dead)

These compose agentwatch + agentpolicy/agentkeys/agenthalt; agentwatch provides the record/replay for each.
