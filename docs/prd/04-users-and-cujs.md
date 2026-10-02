# PRD 04 — Users and Critical User Journeys

**BLUF:** The primary users are platform and security engineers who need **proof of what agents did**
before they will trust any enforcement. The v0.1.0 journey is deliberately small: install, record, replay,
export — on Claude Code, in ≤15 minutes, with zero agent-side code changes.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## Users

| Persona | Who | What they need from agentwatch |
|---|---|---|
| **P1 Maya — platform engineer** | Runs agent tooling for a team | A record that exports to a backend the team already owns; near-zero setup |
| **P2 Ravi — security engineer** | Owned the incident postmortem | A defensible, tamper-evident audit trail; the security-event schema |
| **P4 Sam — solo developer** | One person, many agents | A local audit trail with no cloud dependency |
| **P5 Alex — embedder** (secondary) | Builds agents into a product | An SDK/OTLP path to instrument their framework and emit the schema |

## Users this is *not* for

- Simple chatbots with no tools, state, or long-running behavior.
- Anyone who only wants prompt/completion analytics (that's an LLM observability tool).
- Anyone who wants a dashboard *product* from us — we ship data, not a dashboard.

## User problems

1. **Agent failures are hard to explain.** Even when a run fails or gets expensive, the behavior path is
   unclear.
2. **Generic telemetry is too shallow.** Normal logs/metrics don't capture tool calls, MCP servers,
   replays, or security events.
3. **Nothing is provable after the fact.** Compliance and incident review both fail on "no record".
4. **Signals are fragmented.** Security events, cost, and behavior live in different systems.

## Critical user journeys (v0.1.0)

### CUJ-1 — Install and record (the core journey)
1. Fresh machine with Claude Code. Run `npx @agentsec-ecosystem/cli init`.
2. The CLI installs the Claude Code hooks + local daemon, monitor-only by default.
3. Use Claude Code normally.
4. **Success:** the first tool call is recorded in ≤15 minutes, with **zero changes to the agent or its
   code**, and no secret/PII in the stored record.

### CUJ-2 — Replay a session
1. `agentsec sessions` lists recorded sessions.
2. `agentsec replay <session-id>` reconstructs the ordered action timeline.
3. **Success:** the replay matches the raw transcript in an automated test.

### CUJ-3 — Export to a backend you own
1. Point agentwatch at an OTLP endpoint.
2. Records flow to a standard OTel backend (e.g. Phoenix) unmodified.
3. **Success:** data loads into ≥2 common backends without transformation.

### CUJ-4 — Consume/emit a security event
1. A policy denies a tool call (agentpolicy) or a secret is detected.
2. agentwatch emits the named event (`denied`, `policy-fired`, `secret-detected`, …) in the schema.
3. **Success:** the schema is published, and ≥1 other ecosystem tool emits it.

## Later journeys (not v0.1.0)

- **CUJ-5 — Inventory:** "what agents/MCP servers exist on this machine?" (R9).
- **CUJ-6 — Compare versions:** behavior changed between agent/prompt/model versions (absorbed from
  AgentObservatory).
- **CUJ-7 — Drift:** behavioral drift relative to a trailing baseline (absorbed from AgentWatch; alerting
  lives in agentpolicy).

## Success criteria for v0.1.0 users

CUJ-1 through CUJ-4 pass on a clean machine, and a security engineer can answer "what did that agent do?"
in <5 minutes from a standard backend.
