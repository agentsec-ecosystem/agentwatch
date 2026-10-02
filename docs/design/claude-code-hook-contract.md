# Design — Claude Code Hook Contract

**BLUF:** The exact shape of the Claude Code Pre/PostToolUse hooks, the socket protocol to the daemon, and
the event JSON we normalize. This is what Part 3 of the WBS implements.

Status: **draft** (v0.1.0).

## Hook installation

`agentwatch init` writes hooks into Claude Code's settings (user or project scope) that invoke a small
script which forwards the event to the daemon over a Unix domain socket.

```jsonc
// Claude Code settings (illustrative — confirm against current Claude Code docs at build time)
{
  "hooks": {
    "PreToolUse":  [{ "command": "agentwatch-hook pre  "$CLAUDE_HOOK_EVENT"" }],
    "PostToolUse": [{ "command": "agentwatch-hook post "$CLAUDE_HOOK_EVENT"" }]
  }
}
```

## Event payload (from Claude Code)

Claude Code passes a JSON event via stdin/env containing (confirm exact fields at build time):
- `session_id`, `tool_name`, `tool_input` (arguments), `tool_response` (PostToolUse), `cwd`, `agent`
- timestamps

## Socket protocol (hook → daemon)

- Transport: Unix domain socket at `$XDG_RUNTIME_DIR/agentwatch.sock` (or `/tmp/agentwatch.sock`).
- Framing: newline-delimited JSON; one message per hook event.
- Message: `{ "phase": "pre"|"post", "harness": "claude-code", "event": <claude code event> }`.
- The hook script is fire-and-forget; the daemon acknowledges and normalizes asynchronously.
- Hook failure must not block the agent (return 0); a missed event is recorded as `hook-error` (F2).

## Normalization

`normalize(raw) -> Record[]` produces one record per tool call (pre → intent; post → outcome), per the
[record format spec](../reference/record-format-spec.md). Redaction runs before storage (DD-06).

## Documented gaps (R3)

- Claude Code does not emit explicit session-boundary events in v0.1.0 → we infer from inactivity timeout.
- Some tool arguments may be opaque blobs → recorded under the privacy mode (metadata-only default).

## Conformance

Adapter conformance fixtures (see [adapter-conformance](../reference/adapter-conformance.md)) replay
sampled Claude Code events and assert the normalized records.
