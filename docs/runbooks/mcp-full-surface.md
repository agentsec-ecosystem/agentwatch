# Runbook — MCP full-surface capture (2026-07-28)

Goal: record the full MCP surface — `tools/call`, `resources/read` (+ resource
links), `prompts/get`, elicitation, and `tasks/*` — over **Streamable HTTP**, with
`tool.server` attribution and same redaction/chain pipeline.

```sh
# Re-point MCP servers at the interposition proxy (consent-first; reversible):
agentwatch init --mcp-proxy

# Or run the proxy directly (Streamable HTTP is the default; sessions removed):
agentwatch mcp-proxy --http --transport streamable-http --route github=https://mcp.example/mcp
# Legacy servers: --transport http-sse (kept verbatim, deprecated-in-spec)

# After use — search by surface:
agentwatch search --mcp-resource file:///repo/README.md
agentwatch search --tool tasks/get
```

## Verify

- [ ] `resources/read` and resource links appear (`search --mcp-resource <uri>` finds each access).
- [ ] `prompts/get` records carry the prompt name as metadata.
- [ ] Elicitation records link the answer to approval (`accept`→`user`, `decline`→`denied`, else `unknown`).
- [ ] `tasks/*` records carry the task id; Roots/Sampling/Logging are relayed but not recorded (closed-by-spec, SEP-2577).
- [ ] An unknown method is quarantined and surfaced as harness-drift, never silently dropped.

## Notes

- The streamable transport is **stateless**: `Mcp-Session-Id` is neither required, forwarded, nor emitted.
- `uninstall` restores `.mcp.json`/`~/.claude.json` byte-identically.
- Protocol revisions are versioned fixtures (2025-06-18 / 2025-11-25 / 2026-07-28); drift fails CI.
