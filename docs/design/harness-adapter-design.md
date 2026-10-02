# Design — Harness Adapter Boundary

**BLUF:** A small adapter contract converts a harness's native surface into the agentwatch record format.
Claude Code hooks are the first implementation.

Status: **implemented** for Claude Code (v0.1.0 M3).

## Contract

An adapter module declares:

- a `HARNESS_ID` (e.g. `"claude-code"`);
- its `CAPABILITIES` — the capability classes it implements (e.g. `pre-tool-use`, `post-tool-use`);
- its `DOCUMENTED_GAPS` — capability classes it does **not** implement, declared honestly (R3);
- `normalize(message) -> list[AgentRecord]` mapping one native event to records.

Unsupported capability classes are rejected explicitly (a `ClaudeCodeAdapterError`), never dropped
silently.

## v0.1.0 implementation

`agentwatch.adapters.claude_code`:

| | |
|---|---|
| `HARNESS_ID` | `claude-code` |
| `CAPABILITIES` | `pre-tool-use`, `post-tool-use` |
| `DOCUMENTED_GAPS` | `session-boundaries`, `mcp-server-events` |
| `normalize` | Pre → intent record (`act`); Post → outcome record (`observe`) |

Claude Code `PreToolUse` / `PostToolUse` hooks → local daemon over a local socket
([hook contract](claude-code-hook-contract.md)). PostToolUse captures outcome; PreToolUse captures
intent (enables future enforcement to plug in). Redaction runs before a record is emitted (DD-06).

## Future

- Cursor, Codex CLI, Gemini CLI (config/wrapper).
- Generic MCP clients via proxy tap.
- Frameworks via OTLP/SDK ingestion.
