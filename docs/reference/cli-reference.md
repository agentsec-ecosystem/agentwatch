# Reference — CLI Reference (v0.1.0)

**BLUF:** The `agentwatch` command: install, global flags, subcommands, and how configuration resolves.
M1 wires the framework and every documented subcommand; `status` is implemented and the daemon/store
subcommands are filled in by M3–M5 (they fail closed, with a non-zero exit, until then).

## Install

```sh
pip install agentwatch                 # Python CLI on PyPI
npx @agentsec-ecosystem/cli <command>  # thin launcher that invokes the Python CLI
```

The launcher is equivalent to `agentwatch <command>`. It invokes `python3 -m agentwatch.cli`; set
`AGENTWATCH_PYTHON` to choose another interpreter.

## Global flags

| Flag | Purpose |
|---|---|
| `--config PATH` | Add a config file at the highest file precedence (repeatable). |
| `--set KEY=VALUE` | Override one config key, e.g. `--set log.level=debug` (repeatable). |
| `--version` | Print the version and exit. |
| `-h`, `--help` | Show help for `agentwatch` or any subcommand. |

## Subcommands

| Command | Purpose | M1 status |
|---|---|---|
| `agentwatch init [--scope project\|user] [--no-daemon]` | Install hooks + start the daemon (monitor-only default) | **implemented** (M3) |
| `agentwatch status` | Print the resolved configuration / health summary | **implemented** |
| `agentwatch sessions [--project PATH]` | List recorded sessions | **implemented** (M3; `--project` M9) |
| `agentwatch replay <id>` | Reconstruct a session timeline | **implemented** (M5) |
| `agentwatch export enable/disable` | Opt-in OTLP export (gated on self-test) | **implemented** (M5) |
| `agentwatch verify-store` | Check the store hash chain | **implemented** (M4) |
| `agentwatch verify-privacy` | Verify redaction and scan the store for leaks | **implemented** (M5) |
| `agentwatch tail [-f] [--session-id ID] [--project PATH] [--json] [--alert]` | Read-only record stream; `--alert` marks security signals | **implemented** (M5/M8; `--project` M9) |
| `agentwatch doctor [--json]` | Ordered health checklist with fix hints | **implemented** (M5) |
| `agentwatch view [<id>]` | Terminal timeline: list sessions or show a session | **implemented** (M7) |
| `agentwatch explain <id>` | Deterministic, local-first session summary (no egress by default) | **implemented** (M7) |
| `agentwatch search [--tool T] [--outcome O] [--session S] [--project PATH] [--since WHEN] [--json]` | Filter stored records | **implemented** (M8; `--project` M9) |
| `agentwatch diff <a> <b> [--json]` | Behavioral diff of two sessions | **implemented** (M8) |
| `agentwatch import <path> [--capture MODE] [--json]` | Import Claude Code transcripts (redacted before storage) | **implemented** (M8) |
| `agentwatch inventory [--session-id ID] [--project PATH] [--json]` | List recorded agents + MCP servers (R9) | **implemented** (M9) |
| `agentwatch retention apply [--json]` | Tombstone records older than `store.retention_days` | **implemented** (M9) |
| `agentwatch purge <id> --yes [--reason TEXT]` | Tombstone one session (right to erasure) | **implemented** (M9) |
| `agentwatch migrate [--rollback]` | Store-format migration (v0.2.0+) | wired, implemented in M9+ |
| `agentwatch uninstall [--scope project\|user]` | Remove hooks, stop the daemon | **implemented** (M3) |

## Configuration

`agentwatch` resolves configuration from, lowest to highest precedence:

1. system — `/etc/agentwatch/config.toml`
2. user — `$XDG_CONFIG_HOME/agentwatch/config.toml` (default `~/.config/agentwatch/config.toml`)
3. project — `./.agentwatch/config.toml`
4. environment — `AGENTWATCH_*` (nested keys use a double underscore, e.g. `AGENTWATCH_STORE__RETENTION_DAYS`)
5. CLI flags — `--config` files, then `--set` overrides

Objects merge recursively; scalars are replaced by the higher-precedence source. Loading is **strict and
fail-closed**: an unknown key, an invalid value, or an unsafe export setup prints
`agentwatch: configuration error: …` and exits `2` rather than running with bad settings (F7). An explicit
`--config` file that is missing is also a configuration error. `AGENTWATCH_PYTHON` (the launcher's
interpreter override) is reserved and ignored. See [PRD 16 — Configuration](../prd/16-configuration.md)
for the full key list and defaults.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success. |
| `1` | Install error (e.g. the daemon failed to start). |
| `2` | Configuration error (fail-closed) or a usage error from `argparse`. |
| `3` | A subcommand that is wired but not yet implemented in this milestone. |
