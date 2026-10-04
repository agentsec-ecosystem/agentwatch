# PRD 16 — Configuration Model

**BLUF:** What's configurable, the defaults, where config lives, how it's validated, and the fail-closed rule
when config is bad or tampered. Configuration is a security surface, so it's explicit and validated.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## Where config lives

| Scope | Location | Notes |
|---|---|---|
| System | `/etc/agentwatch/config.toml` (POSIX) | optional; lowest precedence |
| User | `~/.config/agentwatch/config.toml` (`XDG_CONFIG_HOME`) | default user config |
| Project | `.agentwatch/config.toml` | co-located with the agent project; overrides user |
| CLI flags | `agentwatch --flag value` | highest precedence; documented in `--help` |
| Env | `AGENTWATCH_*` | for CI/headless; never logs secrets |

Precedence (low → high): system < user < project < env < CLI flags. Later wins; arrays replace, objects
merge recursively.

## What's configurable (v0.1.0)

| Key | Default | Notes |
|---|---|---|
| `harness` | `claude-code` | which adapter to install |
| `mode` | `monitor` | `monitor` (record only) — enforcement is agentpolicy's job |
| `store.path` | `~/.local/share/agentwatch` | local-first (R6, DD-03) |
| `store.retention_days` | `30` | R11 |
| `store.max_size_mb` | `1024` | size cap (R11) |
| `privacy.mode` | `metadata-only` | one of metadata-only / truncated / hashed / full |
| `redaction.self_test` | `enabled` | must pass before export (DD-09) |
| `export.enabled` | `false` | opt-in (R6) |
| `export.otlp_endpoint` | — | required when export.enabled=true |
| `export.format` | `otel-genai` | only format in v0.1.0 |
| `health.endpoint` | `127.0.0.1:9100` | see PRD 13 self-observability |
| `log.level` | `info` | debug/info/warn/error |

## Validation

- Config is validated on load and on change (file watcher). Invalid config **fails closed**: the daemon
  refuses to start (or stops recording and surfaces the error) rather than running with bad settings.
- Unknown keys are rejected (strict), not silently ignored.
- Secrets are never written to config files; credential material lives in agentkeys, not here.

## Tamper & fail-closed (security)

- Hook/daemon config edits are detected (the ecosystem threat model). On a detected edit, agentwatch
  **fails closed**: recording stops in a state that surfaces the problem, never silently (NFR-8).
- A config change that would disable redaction or enable export without the self-test passing is rejected.
- The daemon's own config is read-only at runtime; changes require a restart and a fresh validation pass.

## Defaults are safe

The out-of-the-box config is **monitor-only, local-first, redacted, no export**. Unsafe options (full privacy
mode, export enabled) require explicit opt-in and surface a warning.
