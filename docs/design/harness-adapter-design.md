# Design — Harness Adapter Boundary

**BLUF:** A small adapter contract converts a harness's native surface into the agentwatch record format.
Claude Code hooks are the first implementation.

Status: **implemented** for Claude Code (v0.1.0 M3) and **Cursor native hooks** (v0.2.0 M25, capture tier
pending 25.CUR-1); Codex CLI and Gemini CLI are **provisional (modeled)** in M10.

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
| Codex CLI | `agentwatch.adapters.codex_cli` | `exec_begin`, `exec_end`, `patch_apply` |
| Gemini CLI | `agentwatch.adapters.gemini_cli` | `tool_call`, `tool_result`, `session_start`, `session_end` |

## Cursor native hooks (v0.2.0 M25, CUR-2)

`agentwatch.adapters.cursor` normalizes Cursor's native `hooks.json` events, framed by the hook binary as
`{"phase": <hook_event_name>, "harness": "cursor", "event": {...}}`. It covers the full loop — session
boundaries, pre/post tool use (incl. failure), shell, MCP, `beforeReadFile`, file edits, subagents, prompt
submission, compaction, `afterAgentThought`/`afterAgentResponse`, Tab hooks, and `workspaceOpen`. Blocking
`before*` events are recorded as observations and **never answered** (monitor-only, R2); the `ide`
environment (`cursor-cli`/`cursor-ide`/`cursor-remote`) is tagged in `environment`; `user_email` becomes
the hashed `principal` (IDN-1); cloud-agent hook gaps are declared (`cloud-agent-hook-events`), never
silent. Field names follow the published contract (`conversation_id`, `generation_id`,
`workspace_roots`, `file_path`, `cursor_version`). The audit corpus (25.CUR-1) is a version-tagged,
secret-scanned, MIT/vendor-documented set under `tests/testkit/` (provenance in
`tests/testkit/PROVENANCE.md`), so the matrix row is `fixture-verified` — `live-verified` awaits a
consented capture.

**CUR-3 coverage reconciliation (M26).** Cursor records are reconciled against ground truth where it exists —
the version-tagged `cursor-session-tracer` corpus under `tests/testkit/cursor/`.
`agentwatch.coverage.discover_cursor_transcripts` / `extract_cursor_trace` read each trace's
`session.cursor_stats.tool_call_count` (fallback: structural file ops) as the per-session ground truth, and the
S2 gap taxonomy gains `gap:cursor-hook-coverage` so a Cursor shortfall (phase-gated IDE/cloud/Tab hooks) is
classified rather than `gap:unexplained`. CLI: `agentwatch coverage --harness cursor [--transcripts DIR]`. The
golden corpus reconciles to zero `unexplained` (`tests/test_cursor_coverage.py`).

## v0.2.0 — capture levels and real harnesses

The v0.2.0 program ([PRD 42](../prd/42-harness-fidelity-and-realtime.md),
[PRD 45](../prd/45-new-capture-surfaces.md)) replaces the "modeled" rows using four capture levels, in
fidelity-per-effort order (PRD 27 strategy):

| Level | Mechanism | Harnesses |
|---|---|---|
| Native hooks | JSON on stdin to a command; same contract as Claude Code | **Cursor** (full loop incl. blocking before-events, `beforeReadFile`, `afterAgentThought`), OpenCode (`tool.execute.before/after`, `session.*`, `file.changed`) |
| Native OTel | built-in telemetry → OTLP/JSON/GCP, ingested | **Gemini CLI** (`telemetry` settings; `active_approval_mode`→approval, `user.email`→hashed principal, `installation.id`/`session.id`→identity — GEM-2) |
| Log-read | read the files the agent already writes | **Codex** (rollout JSONL; `.jsonl.zst`, dangling sessions — reader M27 COD-1), **OpenCode** (storage tree — reader M27 LOG-1), long-tail CLIs |
| Interposition | proxy the wire protocol | MCP (2026-07-28 surface), **A2A** (signed agent cards) |

Contract additions: an adapter declares its **fidelity tier** (`live-verified | fixture-verified | modeled`) and
its **capture level**; blocking-hook events are recorded as observations and **never answered** (monitor-only, R2).
Foreign log/rollout content follows the untrusted-data rule ([ADR-0024](../adr/0024-foreign-data-threat-posture.md)).

**System-effects layer (M29 SYS-1).** A fifth level — the system calls *below* the tool call — is ingested from an
AgentSight/Tracee-shaped foreign stream, **Linux-only and opt-in** (we do not build Linux-root eBPF probes). It is
joined to sessions by process lineage/time-window, every record is labeled `source: system-ingest`, and a lineage
that is not owned by exactly one session is filed under `unjoined:system-ingest` rather than guessed. See
[system-effects-ingest.md](system-effects-ingest.md).

See [cross-harness-testing.md](cross-harness-testing.md) for how compatibility is verified without the CLIs.

## Future

- Full-fidelity CrewAI/PydanticAI adapters (later).
- Generic MCP clients via proxy tap (N1, M10).
- Framework SDKs via OTLP/SDK ingestion (N2).
