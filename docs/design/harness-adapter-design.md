# Design — Harness Adapter Boundary

**BLUF:** A small adapter contract converts a harness's native surface into the agentwatch record format.
Claude Code hooks are the first implementation.

Status: **implemented** for Claude Code (v0.1.0 M3); Cursor, Codex CLI, and Gemini CLI are **provisional
(modeled)** in M10.

## Contract

An adapter module declares:

- a `HARNESS_ID` (e.g. `"claude-code"`);
- its `CAPABILITIES` — the capability classes it implements (e.g. `pre-tool-use`, `post-tool-use`);
- its `DOCUMENTED_GAPS` — capability classes it does **not** implement, declared honestly (R3);
- `normalize(message) -> list[AgentRecord]` mapping one native event to records.

Unsupported capability classes presented to the adapter (a declared-gap or unknown hook phase) are
rejected explicitly with a `ClaudeCodeAdapterError`, never dropped silently.

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

## Provisional harnesses (M10, modeled)

No native event surface is documented in-repo for these harnesses, so each adapter maps an **assumed**
shape and ships synthesized-from-shape fixtures. They are **provisional**: the fixtures and capabilities
are replaced when real captures land (M14 field tests / N4 version matrix). Each registers in the shared
conformance runner with a `mcp-server-events` declared gap.

| Harness | Module | Capability classes |
|---|---|---|
| Cursor | `agentwatch.adapters.cursor` | `beforeShellExecution`, `afterShellExecution`, `beforeFileEdit`, `afterFileEdit` |
| Codex CLI | `agentwatch.adapters.codex_cli` | `exec_begin`, `exec_end`, `patch_apply` |
| Gemini CLI | `agentwatch.adapters.gemini_cli` | `tool_call`, `tool_result`, `session_start`, `session_end` |

## Future

- Full-fidelity Cursor/Codex CLI/Gemini CLI adapters once real events are captured (v0.1.x/later).
- Generic MCP clients via proxy tap (N1, M10).
- Frameworks via OTLP/SDK ingestion (N2).
