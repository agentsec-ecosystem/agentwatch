# PRD 03 — Landscape

**BLUF:** Observability exists for agents, but as per-harness consoles or commercial platforms — not a
vendor-neutral, local-first, security-event-aware open record.

## Adjacent / overlapping

- **OTel GenAI semantic conventions** — emerging standard, Development-grade; we implement and contribute
  upstream (`DD-05`).
- **Per-harness telemetry** (Claude Code, Cursor consoles) — vendor-locked, not exportable.
- **Commercial agent observability** (e.g., Invariant Explorer, cloud APM agent views) — hosted, not
  local-first, and not an open event schema.
- **MCP scanners** (e.g., snyk/agent-scan) — scan/analysis, not a runtime record.

## Whitespace

An **open, versioned security-event schema** + a "just works" OTel GenAI implementation with
redaction-by-default and local-first storage. Adopted by other ecosystem tools and, ideally, by
non-ecosystem tools.
