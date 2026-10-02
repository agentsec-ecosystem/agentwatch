# Design — Claude Code Hook Contract

**BLUF:** The exact shape of the Claude Code Pre/PostToolUse hooks, the socket protocol to the daemon, and
the event JSON we normalize. Implemented for v0.1.0 in M3.

Status: **implemented** (v0.1.0 M3).

## Hook installation

`agentwatch init` writes hooks into Claude Code's settings (user or project scope) that invoke a small
script which forwards the event to the daemon over a Unix domain socket. The M3 scripts are
`agentwatch-hook` (the client Claude Code calls) and `agentwatch-daemon` (the receiver).

```jsonc
// Claude Code settings (illustrative — confirm against current Claude Code docs at build time)
{
  "hooks": {
    "PreToolUse":  [{ "command": "agentwatch-hook pre" }],
    "PostToolUse": [{ "command": "agentwatch-hook post" }]
  }
}
```

`agentwatch-hook` reads the environment/event JSON from **stdin** and always exits `0` so it can never
block the agent; `agentwatch init` wiring is delivered in a later milestone.

## Event payload (from Claude Code)

Claude Code passes a JSON event on stdin containing (fields we consume):
- `session_id`, `tool_name`, `tool_input`, `tool_response` (PostToolUse), `agent`
- `tool_use_id` (correlates Pre → Post), `timestamp`, `duration_ms`

The adapter tolerates missing fields and ignores unknown ones. `agent` may be a string or an object with
`identity` / `name` / `version`.

## Socket protocol (hook → daemon)

- **Transport:** Unix domain socket at `$AGENTWATCH_SOCKET`, else `$XDG_RUNTIME_DIR/agentwatch.sock`,
  else `/tmp/agentwatch.sock`. The daemon creates it owner-only (`0600`).
- **Framing:** newline-delimited JSON; one message per hook event.
- **Message:** `{ "phase": "pre"|"post", "harness": "claude-code", "event": <claude code event> }`.
- **Sink (M3):** the daemon appends normalized records to `<store.path>/records.jsonl` (the hash-chained
  store of M4 replaces this sink).
- The hook is fire-and-forget; the daemon normalizes asynchronously. A malformed hook input sends a
  `"phase": "hook-error"` frame instead.

## Normalization

`agentwatch.adapters.claude_code.normalize(message) -> list[AgentRecord]` produces one record per tool
call: Pre → an intent record (`step_type="act"`, no end); Post → an outcome record
(`step_type="observe"`, `outcome="ok"|"error"`, end time and duration). Both share a `span_id` when the
event carries a `tool_use_id`. Redaction runs here, before a record leaves the adapter (DD-06); the
default is metadata-only (no argument content).

## Hook failure (F2)

A hook failure must not block the agent (exit 0). The missed tool call is **recorded, never dropped**, as
a record with `outcome="error"` and `tool.name="hook-error"`. The daemon synthesizes one when a Post
arrives with no matching Pre (or a Pre never pairs), and the hook sends an explicit `hook-error` frame on
malformed input.

## Documented gaps (R3)

- Claude Code does not emit explicit session-boundary events in v0.1.0 → session boundaries are a declared
  gap (`session-boundaries`); they are inferred from inactivity in a later milestone.
- MCP server attribution (`mcp-server-events`) is not available from these hooks.
- Some tool arguments may be opaque blobs → recorded under the privacy mode (metadata-only default).

## Conformance

Adapter conformance fixtures live in `packages/python-sdk/tests/fixtures/claude-code/` and replay native
hook messages to expected records (`tests/test_conformance.py`); declared-unsupported capability classes
are rejected explicitly, never dropped. See [adapter-conformance](../reference/adapter-conformance.md).
