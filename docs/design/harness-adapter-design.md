# Design — Harness Adapter Boundary

**BLUF:** A small adapter contract converts a harness's native surface into the agentwatch record format.
Claude Code hooks are the first implementation.

Status: **draft**.

## Contract (sketch)

An adapter declares: harness id, capabilities (pre/post tool-use, MCP events, session boundaries), and a
`normalize(raw) -> Record[]` mapping. Unsupported capability classes are declared as documented gaps
(honesty requirement, R3).

## v0.1.0 implementation

- Claude Code `PreToolUse` / `PostToolUse` hooks → local daemon over a local socket.
- PostToolUse captures outcome; PreToolUse captures intent (enables future enforcement to plug in).

## Future

- Cursor, Codex CLI, Gemini CLI (config/wrapper).
- Generic MCP clients via proxy tap.
- Frameworks via OTLP/SDK ingestion.
