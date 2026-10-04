# Reference — Known Limitations

**BLUF:** Honest gaps, including those inherited from the shipped project. Published, not hidden.

Status: living.

## Inherited from `agent-exec-trace` (shipped)

- Batch polling only (~30 s ingestion delay), not streaming.
- No distributed trace correlation across services.
- No multi-tenant isolation.
- LLM detectors were research-grade (10-trace sample).
- 28/35 detectors silent on the HF field-test corpus (structurally dependent on tool-use semantics).
- No PydanticAI adapter; no policy-overlay view; no memory-audit UI.

## agentwatch-specific (v0.1.0)

- Claude Code is fully supported (v0.1.0 M3). Cursor, Codex CLI, Gemini CLI, and the Tier-2 frameworks
  CrewAI and PydanticAI have **provisional (modeled)** adapters in v0.1.0 — their native event shapes are
  assumed, not captured; full-fidelity support and real fixtures land in v0.1.x/later (M14 field tests /
  N4 version matrix). Their generated compatibility rows read "modeled" until real captures land.
- MCP interposition (`agentwatch mcp-proxy`, M10 N1) records `tools/call` over **stdio and HTTP/SSE**;
  `agentwatch init --mcp-proxy` re-points `.mcp.json`/`~/.claude.json` and `uninstall` restores it
  byte-identically. MCP `resources`/`prompts`/`sampling` are relayed but not recorded (declared gaps).
  HTTP mode holds each forwarded request/response in memory (bounded by the upstream body); a truly
  unbounded SSE stream is relayed while open but only its `data:` frames are parsed.
- OTel/NDJSON ingestion (`agentwatch ingest`, M10 N2) is a **transcoder, not a general OTel backend**
  (D-Q): it maps GenAI spans/attributes onto records + security events and quarantines what does not
  normalize. OTLP JSON and newline-delimited JSON only — not OTLP/gRPC or protobuf — and a huge OTLP JSON
  document is loaded whole (NDJSON streams line-by-line).
- Compatibility/version matrix (M10 N4) fingerprints the *shape* of conformance fixtures; a field addition
  counts as drift and is surfaced for a human review, not auto-applied. Modeled adapters have no real
  version range yet ("modeled").
- Hash chain is detect-only (no signing key) at v0.1.0.
- Security-event schema v1 is draft; naming may move upstream to OTel (DD-14).

## Policy

A limitation enters this file when it is discovered and leaves it only when a test proves it closed.
