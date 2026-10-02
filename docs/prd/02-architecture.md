# PRD 02 — Architecture

**BLUF:** Harness hooks / MCP taps feed a local daemon that normalizes events into the agentwatch record
format (OTel GenAI spans + the security-event schema) and stores them locally by default.

## Components (v0.1.0)

- **Harness adapters** — begin with Claude Code `PreToolUse`/`PostToolUse` hooks. Adapter boundary is a
  contract (`DD-04`), so Cursor/Codex/Gemini follow without redesign.
- **Local daemon** — receives hook events, normalizes, redacts, and writes records.
- **Record format** — tool-call records + named security events; versioned schema (`design/record-format-design.md`).
- **Local store** — local-first; the user's data leaves the machine only if they configure export (`DD-03`).
- **Exporters** — OTLP (Phoenix, Splunk, Datadog); "we ship data, not a dashboard."
- **CLI** — install/setup, status, replay (`agentsec init`, `agentsec replay`).

## Boundary

agentwatch **records and exposes only**. It performs no alerting and no injection/behavioral/intent
analysis — those belong to agentpolicy and agentdrill. See [PRD 05](05-features.md) non-requirements.
