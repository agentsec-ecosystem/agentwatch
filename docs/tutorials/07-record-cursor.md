# Tutorial 07 — Record Cursor

Cursor ships `hooks.json` and can invoke external programs across its whole agent
loop. agentwatch's Cursor adapter normalizes those payloads into records — reads,
edits, reasoning, subagents, prompt submission, compaction, and MCP.

## 1. Point Cursor hooks at agentwatch

Configure `.cursor/hooks.json` (project) or `~/.cursor/hooks.json` (user) so each
event calls the agentwatch hook command (the exact hook list is in
[harness-adapter-design.md](../design/harness-adapter-design.md)).

## 2. Use Cursor, then look

```sh
agentwatch sessions
agentwatch replay <session-id>
agentwatch coverage --harness cursor
```

## 3. What you should see

- `preToolUse`/`postToolUse` pairs sharing a `span_id`; `beforeReadFile` as a read step;
  `afterAgentThought` as reasoning; `afterFileEdit` as an edit.
- Blocking events are recorded as **observations**, never answered — recording never gates the agent.
- Cloud agents are a declared gap (no session hooks).

See the [runbook](../runbooks/cursor-install-and-verify.md) for the verification checklist.
