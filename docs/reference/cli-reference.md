# Reference — CLI Reference (v0.1.0)

**BLUF:** Finalized subcommand names used across the docs.

| Command | Purpose |
|---|---|
| `agentwatch init` | install hooks + start daemon (monitor-only default) |
| `agentwatch status` | health summary (PRD 13) |
| `agentwatch sessions` | list recorded sessions |
| `agentwatch replay <id>` | reconstruct a session timeline |
| `agentwatch export enable/disable` | opt-in OTLP export (gated on self-test) |
| `agentwatch verify-store` | check the hash chain |
| `agentwatch migrate [--rollback]` | store-format migration (v0.2.0+) |
| `agentwatch uninstall` | remove hooks, stop daemon |

The npx launcher exposes the same commands: `npx @agentsec-ecosystem/cli <command>`.
