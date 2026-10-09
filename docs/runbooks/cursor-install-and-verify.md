# Runbook — Cursor install & verify

Goal: record Cursor's full agent loop (native hooks) and confirm it.

Cursor invokes external programs from `hooks.json` with JSON on stdin across the
whole loop (`preToolUse`/`postToolUse`, `beforeReadFile`, `afterFileEdit`,
subagents, prompt submission, compaction, `afterAgentThought`). agentwatch's
Cursor adapter normalizes those payloads.

```sh
# 1. Point Cursor hooks at the agentwatch hook command.
#    Project: .cursor/hooks.json   User: ~/.cursor/hooks.json
#    (see docs/design/harness-adapter-design.md for the exact hook list)

# 2. Record normally, then confirm a session landed:
agentwatch sessions
agentwatch replay <session-id>

# 3. Reconcile coverage against Cursor transcripts (where ground truth exists):
agentwatch coverage --harness cursor
```

## Verify

- [ ] `agentwatch sessions` shows a Cursor session after a tool call.
- [ ] `agentwatch replay <id>` reconstructs reads/edits/reasoning steps.
- [ ] `agentwatch coverage --harness cursor` reports no unexplained gaps.

## Notes / limitations

- Blocking hook events are **recorded as observations, never answered** (monitor-only).
- Cursor cloud agents (`cursor.com/agents`) do not run `sessionStart`/`sessionEnd`/MCP/Tab/
  `workspaceOpen` hooks — a declared gap, not a silent one.
- The matrix row is **fixture-verified** until a consented live capture lands; there is no
  shell/eval on any reader path (untrusted-data rule, ADR-0024).
