# Reference — CLI Reference (v0.1.0)

**BLUF:** The `agentwatch` command: install, global flags, subcommands, and how configuration resolves.
M1 wires the framework and every documented subcommand; `status` is implemented and the daemon/store
subcommands are filled in by M3–M5 (they fail closed, with a non-zero exit, until then).

## Install

```sh
pip install agentsec-agentwatch        # Python CLI on PyPI (import + CLI: agentwatch)
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
| `agentwatch init [--scope project\|user] [--profile solo\|team\|compliance\|ci] [--no-daemon] [--service] [--mcp-proxy] [--mcp-scope project\|user] [--mcp-servers A,B] [--mcp-port N]` | Install hooks + start the daemon; `--profile` applies a named config bundle consent-first; `--service` writes a launchd/systemd user unit (opt-in); `--mcp-proxy` also re-points MCP server config at the interposition proxy (monitor-only default) | **implemented** (M3; `--service` M12; `--mcp-proxy` M10; `--profile` M21) |
| `agentwatch status` | Print the resolved configuration / health summary | **implemented** |
| `agentwatch config explain [KEY] [--diff] [--json]` | Show each config key's effective value, winning precedence layer, and overrides (S34 M21) | **implemented** (M21) |
| `agentwatch access log --owner ID [--json]` | Self-visible access log: who (by role) read my records, and when — every cross-user read is a `store-access` record | **implemented** (M29 ACC-1) |
| `agentwatch access check --role R --data-class D --owner ID [--reader ID] [--same-team] [--content] [--json]` | Evaluate one role × data-class read against the model, record it, and deny (nonzero) a read outside the matrix | **implemented** (M29 ACC-1) |
| `agentwatch access matrix [--json]` | Print the published role × data-class matrix | **implemented** (M29 ACC-1) |
| `agentwatch governance notice [--json]` | Render what is recorded/not, who can see it, retention, and erasure **from the live effective config**; every statement maps to a config key or guarantee, unbackable claims are listed as refused, and a "not legal advice" banner is always shown | **implemented** (M29 ACC-2) |
| `agentwatch hold add --scope session:<id>\|project:<path>\|principal:<id>\|time:<a>..<b> --reason TEXT [--ref R] [--json]` / `hold list [--json]` / `hold release <id> [--reason TEXT] [--json]` | Legal holds: while active, retention skips held records and `purge` fails closed; holds/releases are chain records | **implemented** (M29 HLD-1) |
| `agentwatch union [--session-id ID] [--source hook\|sdk] [--json]` | Read-time union of hook records and SDK spans; `source` + chain-protection stated (S11 M21) | **implemented** (M21) |
| `agentwatch checkpoint export [--sign] [--tsa URL] [--output PATH] [--json]` | Emit the latest checkpoint digest; optional ed25519 signature and RFC 3161 token (W7/W9 M22) | **implemented** (M22) |
| `agentwatch checkpoint verify FILE --public-key PATH [--json]` | Verify a signed checkpoint export with a raw ed25519 public key (W9 M22) | **implemented** (M22) |
| `agentwatch redact [--preview SAMPLE] [--mode MODE] [--json]` | Preview redaction, or filter stdin→stdout with findings on stderr (S13 M21) | **implemented** (M15; filter M21) |
| `agentwatch sessions [--project PATH] [--tag NAME]` | List recorded sessions | **implemented** (M3; `--project` M9; `--tag` M15) |
| `agentwatch replay <id> [--receipts] [--trace] [--json]` | Reconstruct a session timeline; `--receipts` shows what redaction did per record (M15 S32); `--trace` expands across hosts/sessions sharing a trace id (M26 TRACE-2) | **implemented** (M5; receipts M15; trace M26) |
| `agentwatch redact --preview SAMPLE [--json]` | Run a sample through the active redaction config (before/after, stores nothing) | **implemented** (M15 S32) |
| `agentwatch export enable/disable` | Opt-in OTLP export (gated on self-test) | **implemented** (M5) |
| `agentwatch export-session <id> [--format ndjson\|ocsf\|cloudevents\|aat] [--output PATH]` | Export one session; OCSF/CloudEvents transcode its security events (S8 M20); `aat` emits the IETF Agent Audit Trail bundle with its chain segment (AAT-2) | **implemented** (M13; M20; M25) |
| `agentwatch verify-store [--repair --yes]` | Check the store hash chain; `--repair` rebuilds from the intact prefix, preserving corrupt evidence (F4) | **implemented** (M4; repair M12) |
| `agentwatch verify-release [DIR] [--checksums PATH] [--sbom PATH] [--allow-unsigned] [--json]` | Verify a built release: checksums, CycloneDX SBOM, and keyless cosign / SLSA provenance | **implemented** (M14 Q13) |
| `agentwatch verify-privacy` | Verify redaction and scan the store for leaks | **implemented** (M5) |
| `agentwatch tail [-f] [--session-id ID] [--project PATH] [--json] [--alert]` | Read-only record stream; `--alert` marks security signals | **implemented** (M5/M8; `--project` M9) |
| `agentwatch doctor [--json]` | Ordered health checklist with fix hints | **implemented** (M5) |
| `agentwatch view [<id>]` | Terminal timeline: list sessions or show a session | **implemented** (M7) |
| `agentwatch explain <id>` | Deterministic, local-first session summary (no egress by default) | **implemented** (M7) |
| `agentwatch search [--tool T] [--outcome O] [--session S] [--project PATH] [--producer KIND] [--approval A] [--identity HANDLE] [--mcp-resource URI] [--memory] [--since WHEN] [--json]` | Filter stored records; `--identity` matches any agent/principal/workload/delegation handle; `--mcp-resource` matches records that read or link an MCP resource URI; `--memory` shows agent memory read/write/delete records (M8; `--project` M9; `--producer` M15; `--approval` M19; `--identity` M26 IDN-2; `--mcp-resource` M27 MCP-2; `--memory` M28 DET-7) | **implemented** (M8; identity M26; mcp-resource M27; memory M28) |
| `agentwatch diff <a> <b> [--json]` | Behavioral diff of two sessions | **implemented** (M8) |
| `agentwatch import <path> [--capture MODE] [--json]` | Import Claude Code transcripts (redacted before storage) | **implemented** (M8) |
| `agentwatch ingest <path> [--format otel\|otlp-grpc\|ndjson\|aat\|claude-compliance\|claude-otel\|system-ingest\|acs] [--agent codex\|opencode] [--consent] [--capture MODE] [--json]` | Ingest foreign OTel GenAI / NDJSON / AAT traces, a Claude Compliance API export (`--format claude-compliance --consent`), Claude Code native OTel (`--format claude-otel`), the Linux-only opt-in system-effects layer (`--format system-ingest --consent`), an ACS Guardian audit trail (`--format acs`), or a harness's native logs (`--agent codex/opencode`; redacted, chained, quarantines unmappable input) | **implemented** (M10 N2; `--format aat` M26; `--agent codex/opencode` + `claude-compliance` M27 COD-1/LOG-1/CCA-1; `claude-otel` M29 CCO-1; `system-ingest` + `acs` M29 SYS-1/ACS-1) |
| `agentwatch fleet ingest HOST=PATH ...` / `fleet show [--json] [--no-group-by-host]` | Opt-in multi-host fleet aggregation (R13) | **implemented** (M11) |
| `agentwatch drift --metric M [--bucket session\|hour] [--window N] [--z-threshold Z] [--emit] [--deploys FILE] [--json]` | Trailing-baseline drift signals, optional `drift-detected` events + deployment correlation | **implemented** (M11) |
| `agentwatch inventory [--session-id ID] [--project PATH] [--snapshot] [--diff] [--server NAME] [--json]` | List recorded agents + MCP servers; `--snapshot`/`--diff` show tool-surface drift (R9; S4 M20) | **implemented** (M9; M20) |
| `agentwatch retention apply [--profile P] [--dry-run] [--json]` | Tombstone records older than the retention window: a named profile (`high-risk-12mo` 365d / `general-6mo` 180d / `custom` = `store.retention_days`); the change is recorded (S5); `--dry-run` reports what would be tombstoned and lists records a legal hold skips (+ hold IDs) | **implemented** (M9; profiles M28 CMP-3; `--dry-run`/holds M29 HLD-1) |
| `agentwatch purge <id> --yes [--reason TEXT] [--override-reason TEXT]` | Tombstone one session (right to erasure); **fails closed** on an active legal hold, `--override-reason` records a conspicuous override | **implemented** (M9; holds M29 HLD-1) |
| `agentwatch evidence <session-id> [--out PATH] [--include-bom] [--include incident-report.json] [--redact-paths]` | Build a self-contained, offline-verifiable bundle (the report is registry-shaped + redacted; no auto-egress) | **implemented** (M15 S1; incident report M28 COR-3) |
| `agentwatch evidence verify bundle.zip` | Re-verify a bundle offline (intact/complete/leak-free) | **implemented** (M15 S1) |
| `agentwatch-verify <bundle.zip\|store.jsonl>` | Standalone stdlib verifier (zipapp), no install | **implemented** (M15 S12) |
| `agentwatch bom [--session-id ID \| --project PATH \| --machine] [--format cyclonedx\|json]` | Agent Bill of Materials, observed (CycloneDX 1.5) | **implemented** (M15 S9) |
| `agentwatch annotate <id> --note TEXT [--tag NAME]` | Append an operator note in the chain (M15 S20) | **implemented** (M15) |
| `agentwatch coverage [--since WHEN] [--project PATH] [--session ID] [--transcripts DIR] [--harness claude-code\|cursor] [--json]` | Reconcile the store against transcript ground truth; classify every gap by cause (M16 S2; Cursor tracer ground truth M26 CUR-3) | **implemented** (M16; cursor M26) |
| `agentwatch compliance report [--framework F] [--period P] [--out FILE] [--json]` | Offline compliance report: control → evidence → verdict → refs + retention/signature status; `--framework owasp-asi-2026` renders the ASI + AST10 coverage map (what the record evidences / command / cannot evidence / tier); never certifies (M26 CMP-1; ASI M29 ASI-1) | **implemented** (M26; `owasp-asi-2026` M29) |
| `agentwatch quarantine list\|inspect <id>\|requeue [--all]\|clear --yes` | Operator tooling for the dead-letter queue; `inspect` redacted by default, `--raw` audited (M16 S27) | **implemented** (M16) |
| `agentwatch archive --before DATE [--out DIR] [--json]` | Seal an old chain prefix into an independently verifiable segment + anchor (M16 S28) | **implemented** (M16) |
| `agentwatch impact <id> [--since WHEN] [--json]` | A session's change footprint / blast radius (M17 S3) | **implemented** (M17) |
| `agentwatch blame <path> [--since WHEN] [--project PATH] [--sessions] [--json]` | File-centric reverse index: who touched a path, newest first (M17 S18) | **implemented** (M17) |
| `agentwatch tree <id> [--by-cost] [--json]` | Subagent fan-out with per-node counts/outcomes/tokens (M17 S17) | **implemented** (M17) |
| `agentwatch at "TIME" [--window 30m] [--json]` | Every record in a cross-session time window, with a gap header (M17 S24) | **implemented** (M17) |
| `agentwatch trace <trace_id> [--json]` | Reconstruct one causal chain across hosts/sessions by `traceparent`, surfacing clock skew and propagation breaks (M26 TRACE-2) | **implemented** (M26) |
| `agentwatch cost [--by session\|project\|model\|tool\|day] [--since 30d] [--json]` | Token/cost rollup against a versioned local pricing table; prefers exact gateway-reported cost and stamps each row exact vs estimated (M17 S6; GWY-2 M26) | **implemented** (M17; gateway cost M26) |
| `agentwatch digest [--since 7d]` | Local markdown weekly readout (sessions/tools/cost/gaps) (M17 S37) | **implemented** (M17) |
| `agentwatch sessions --group-by-behavior` | Group sessions by their `bd1:` behavior fingerprint (M17 S7) | **implemented** (M17) |
| `agentwatch flow <id> [--record] [--json]` | Content → argument flow edges (keyed HMAC; fingerprints only) (M18 S22) | **implemented** (M18) |
| `agentwatch secrets [--session-id ID] [--json]` | Trace exposed secrets across a session without values (M18 S23) | **implemented** (M18) |
| `agentwatch demo [--purge] [--json]` | Prove the hook→daemon→store→chain pipeline with synthetic events (M19 S31) | **implemented** (M19) |
| `agentwatch mcp-proxy --server NAME -- <command> [args...]` | Run the stdio MCP interposition proxy | **implemented** (M10) |
| `agentwatch mcp-proxy --http [--host H] [--port P] [--transport streamable-http\|http-sse] --route NAME=URL ...` | Run the loopback MCP interposition proxy (`streamable-http` default, stateless; `http-sse` legacy, deprecated-in-spec) | **implemented** (M10; Streamable HTTP M27 MCP-1) |
| `agentwatch migrate [--rollback]` | Store-format migration (v0.2.0+) | wired, implemented in M9+ |
| `agentwatch uninstall [--scope project\|user] [--mcp-scope project\|user]` | Remove hooks, stop the daemon, restore MCP config byte-identically, stop the MCP proxy | **implemented** (M3; MCP M10) |

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

Exit statuses come from the one [error contract](errors.md): every failure emits a machine-readable
envelope with a stable `code`, and the code's process status is fixed by the catalog. `0` is success; a
failure is `1` (runtime/install/input), `2` (configuration or usage), or `3` (not implemented). The full
code→exit table is generated in [errors.md](errors.md#exit-codes).
