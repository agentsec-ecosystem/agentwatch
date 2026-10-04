# Tutorial 01 — Getting Started

**BLUF:** Install agentwatch, record your first Claude Code session, and replay it.

Status: **draft** (commands are the intended UX; the CLI ships with v0.1.0).

```sh
# install the hooks + local daemon (monitor-only)
npx @agentsec-ecosystem/cli init

# ... use Claude Code normally ...

# list recorded sessions
agentsec sessions

# replay a session's tool-call timeline
agentsec replay <session-id>
```

Export is opt-in: point agentwatch at an OTLP endpoint and your records flow to a backend you already own.
