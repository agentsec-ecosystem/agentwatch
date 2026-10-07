# ADR-0025 — A2A interposition

- **Status:** proposed (2026-10-05, v0.2.0)
- **Context:** see [PRD 45](../prd/45-new-capture-surfaces.md) A2A-1..2. A2A v1.0 (Linux Foundation / AAIF, beside
  MCP) standardizes agent↔agent tasks and **signed agent cards**; cross-org delegation is where non-repudiation
  breaks down.
- **Decision:** Add an A2A interposition proxy recording task lifecycle, messages, artifacts, and agent-card
  exchanges; treat signed-card identity as a **recorded verification outcome** (`verified`/`unverified`), never as an
  authorization; emit an `agent-delegation` observation; extend `tree`/`trace` across org boundaries.
- **Consequences:** The record layer covers agent↔tools (MCP) and agent↔agent (A2A); card verification is
  evidence-only; consent-first install + byte-identical restore hold; spec is young → version-pin + drift.
- **Implemented (M29 A2A-1/2, 2026-10-06):** `agentwatch a2a-proxy` (stdio + HTTP relay; tasks/messages/artifacts
  + agent-card exchanges), consent-first `a2aAgents` install with byte-identical restore, `agentwatch.agent_card`
  deterministic JWS verification recording `verified`/`unverified`, and an `agent-delegation` observation extending
  `tree`/`trace` across orgs. Tests: `packages/python-sdk/tests/test_a2a_*.py`.
