# PRD 00 — Press Release / FAQ (working backwards)

**BLUF:** The Amazon "working backwards" PR/FAQ. If the headline doesn't land, the release isn't ready.

## Press release

**agentwatch records every tool call your AI agent makes — in OpenTelemetry, on your machine, in 15 minutes.**

Today we're releasing **agentwatch**, an open-source (Apache-2.0) recorder for AI-agent behavior. It writes
what agents actually do — every tool call, in OpenTelemetry GenAI format — to a local store you control, and
defines the open security-event schema the rest of the [agentsec-ecosystem](https://github.com/agentsec-ecosystem)
builds on.

"Most teams can tell you a service is up. Almost none can tell you why an agent looped, overused a tool, or
burned budget," said Debashish Ghosal. "agentwatch makes agent behavior inspectable — and it's the record
every other security control needs."

agentwatch supersedes and consolidates our earlier `agent-exec-trace` work: the instrumentation SDK, the
detector engine, the operator views, and the local stack all return, now with a security-event schema and
coding-agent coverage.

## FAQ

- **Isn't this just LLM observability?** No. Those track individual model calls; agentwatch records agent
  **behavior** and emits **security events**.
- **Does my data leave my machine?** No. Local-first; export is opt-in and gated on a redaction self-test.
- **What does it cost?** Nothing. Apache-2.0, no paywalled enforcement, no proprietary formats.
- **What harnesses?** Claude Code first; Cursor, Codex CLI, Gemini CLI, and frameworks follow.
- **How is it different from the earlier tool we retired?** It's a superset: same instrumentation/detectors/UI,
  plus the security-event schema, coding-agent hooks, and a hardened local store.
