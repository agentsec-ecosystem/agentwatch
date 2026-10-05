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

## v0.2.0 — capture levels and real harnesses

The v0.2.0 program ([PRD 42](../prd/42-harness-fidelity-and-realtime.md),
[PRD 45](../prd/45-new-capture-surfaces.md)) replaces the "modeled" rows using four capture levels, in
fidelity-per-effort order (PRD 27 strategy):

| Level | Mechanism | Harnesses |
|---|---|---|
| Native hooks | JSON on stdin to a command; same contract as Claude Code | **Cursor** (full loop incl. blocking before-events, `beforeReadFile`, `afterAgentThought`), OpenCode (`tool.execute.before/after`, `session.*`, `file.changed`) |
| Native OTel | built-in telemetry → OTLP/JSON/GCP, ingested | **Gemini CLI** (`telemetry` settings; approval + principal attributes) |
| Log-read | read the files the agent already writes | **Codex** (rollout JSONL; `.jsonl.zst`, dangling sessions), long-tail CLIs |
| Interposition | proxy the wire protocol | MCP (2026-07-28 surface), **A2A** (signed agent cards) |

Contract additions: an adapter declares its **fidelity tier** (`live-verified | fixture-verified | modeled`) and
its **capture level**; blocking-hook events are recorded as observations and **never answered** (monitor-only, R2).
Foreign log/rollout content follows the untrusted-data rule ([ADR-0024](../adr/0024-foreign-data-threat-posture.md)).

See [cross-harness-testing.md](cross-harness-testing.md) for how compatibility is verified without the CLIs.

## Future

- Full-fidelity CrewAI/PydanticAI adapters (later).
- Generic MCP clients via proxy tap (N1, M10).
- Framework SDKs via OTLP/SDK ingestion (N2).
