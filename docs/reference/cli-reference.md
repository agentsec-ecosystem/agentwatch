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
| `agentwatch sessions` | List recorded sessions | **implemented** (M3) |
| `agentwatch replay <id>` | Reconstruct a session timeline | wired, implemented in M5 |
| `agentwatch export enable/disable` | Opt-in OTLP export (gated on self-test) | wired, implemented in M5 |
| `agentwatch verify-store` | Check the store hash chain | wired, implemented in M4 |
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
