# PRD 04 — Users and Critical User Journeys

**BLUF:** The primary users are platform and security engineers who need **proof of what agents did**
before they will trust any enforcement. The v0.1.0 journey is deliberately small: install, record, replay,
export — on Claude Code, in ≤15 minutes, with zero agent-side code changes. The v0.1.0 additions extend it to
**evidence hand-off, trust proof, cost, SDK union, erasure, MCP drift, and approval provenance** (CUJ-8–14,
PRDs 31–39).

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

### CUJ-8 — Investigate an incident and hand over evidence (P2 Ravi) · **the flagship journey**
1. `agentwatch search --tool Bash --outcome error --since 2d` finds the suspect session.
2. `agentwatch impact <id>` (S3) shows the footprint: files, commands, hosts, git refs.
3. `agentwatch replay <id>` / `view` walks the sequence; `explain` narrates it.
4. `agentwatch coverage --session <id>` (S2) confirms nothing was missed.
5. `agentwatch evidence <id> --out incident-4471.zip` (S1).
6. **Success:** a third party verifies the bundle offline, on a different machine, without installing
   agentwatch, and the three verdicts (intact / complete / leak-free) are unambiguous.

*Why it matters:* this is the product's value proposition executed end to end; today it stops at step 3 and
J3 (the investigation cookbook) has nowhere to go next.

### CUJ-9 — Prove the recorder deserves trust (P1/P2)
1. `agentwatch doctor` — environment and install are sane.
2. `agentwatch verify-store` — the chain is intact.
3. `agentwatch verify-privacy` — zero leaks under *my* config and *my* store.
4. `agentwatch coverage` (S2) — capture rate, with every gap classified.
5. **Success:** four commands produce one shareable trust report; `gap:unexplained` is zero. A security
   engineer can run this *before* adopting, and an auditor *during* review.

### CUJ-10 — Answer "what did our agents cost last week?" (P1 Maya)
1. `agentwatch cost --by project --since 7d` (S6), then `--by tool` to find the driver.
2. `agentwatch diff` the expensive session against a cheap one.
3. **Success:** answered in one command with no services running, with the pricing-table version stamped in the
   output.

### CUJ-11 — Instrument my own agent and see it beside the harness records (P5 Alex)
1. Add `@trace_agent` to a framework agent (parity SDK).
2. Point it at the local collector; `agentwatch sessions` lists the run with `source: sdk` (S11).
3. The same operator UI shows harness and SDK activity side by side, integrity distinction visible.
4. **Success:** P5 finally has a journey, and the "one install, one format" claim is demonstrable rather than
   aspirational.

### CUJ-12 — Erase on request and prove it (P1/P2)
1. `agentwatch purge <id> --reason "subject request" --yes` (shipped).
2. `agentwatch verify-store` — chain still green, tombstones and the purge marker enumerated.
3. `agentwatch evidence <id>` — a bundle that *proves the erasure happened* without resurrecting the content.
4. **Success:** a defensible erasure record — the GDPR/DSAR shape, and the thing "tombstone, never hard
   delete" (D-K) was built for but never surfaced as a journey.

### CUJ-13 — Notice an MCP server changed under me (P2)
1. `agentwatch inventory --diff --server payments` (S4).
2. A `tool-surface-changed` event names added/removed tools with first/last-seen timestamps.
3. **Success:** a rug-pull is *provable after the fact* — the exact claim `01-why.md:27` makes.

### CUJ-14 — Answer "did a human approve that?" (P2 Ravi)
1. `agentwatch search --approval user --since 30d` (S14) lists every call a person authorized.
2. `agentwatch blame <path>` (S18) shows who touched the file that broke, and under what approval.
3. `agentwatch tree <id>` (S17) shows which subagent did it, since subagents are where responsibility
   currently vanishes.
4. **Success:** for any destructive action in the record, the answer is `user`, `auto`, `not-required`, or an
   honest `unknown` — never an inference.

*Why it matters:* the record answers "what happened" and cannot yet answer "who allowed it," which is the
question that decides whether an incident is a bug or a process failure.

## Later journeys (not v0.1.0)

- **CUJ-5 — Inventory:** "what agents/MCP servers exist on this machine?" (R9).
- **CUJ-6 — Compare versions:** behavior changed between agent/prompt/model versions (absorbed from
  AgentObservatory).
- **CUJ-7 — Drift:** behavioral drift relative to a trailing baseline (absorbed from AgentWatch; alerting
  lives in agentpolicy).

## Success criteria for v0.1.0 users

CUJ-1 through CUJ-4 and the v0.1.0 additions CUJ-8–14 pass on a clean machine, and a security engineer can
answer "what did that agent do?" in <5 minutes from a standard backend — and can hand a third party an evidence
bundle they can verify offline (CUJ-8).
