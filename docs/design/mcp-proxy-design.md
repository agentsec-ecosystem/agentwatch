# Design — MCP-Client Interposition Proxy

**BLUF:** One opt-in local proxy sits between any MCP-speaking harness and its MCP servers, forwarding
traffic unchanged while recording every `tools/call` request/response as agentwatch records with full
`tool.server` attribution. It speaks the **Streamable HTTP** transport (2026-07-28, stateless) and keeps the
legacy HTTP/SSE relay verbatim. It reuses the shipped adapter, redaction, chain, and conformance boundaries;
install is consent-first and uninstall restores the harness config byte-for-byte.

Status: **accepted** (2026-10-03; Plan A + Plan B landed) · **Milestone:** M10 Phase 3 (WBS 10.5 / 10.N1) ·
**M27 MCP-1** (Streamable HTTP transport) · **Issues:** #83 (M10 10.5),
#212 (N1), #333 (M27 MCP-1) · **Decision:** D-P · **PRDs:** [27](../prd/27-harness-expansion.md#n1-mcp-client-interposition-adapter-one-adapter-n-harnesses--m10-212),
[11](../prd/11-decisions.md), [25](../prd/25-capture-fidelity.md), [23](../prd/23-event-interchange.md)

## Goal

Give any MCP-speaking harness the cheapest broad-fidelity recording path — one adapter for many harnesses —
and fill the `mcp-server-events` gap (declared by the Claude Code adapter) plus R9 inventory from live traffic,
not just tool names.

## Scope

- **In scope (v0.1.0):** stdio MCP servers and HTTP/SSE MCP servers; recording `tools/call` traffic; consent-first
  config re-pointing; byte-exact restore; conformance registration.
- **In scope (v0.2.0 MCP-1):** the HTTP relay speaks the **Streamable HTTP** transport as its default
  (`--transport streamable-http`); the legacy HTTP/SSE relay is kept verbatim (`--transport http-sse`,
  deprecated-in-spec).
- **Out of scope (declared gaps):** MCP `resources/read`, `prompts/get`, sampling, and elicitation are relayed
  but **not** recorded (no record-model concept yet); non-MCP harnesses fall back to native/OTel (N2). The
  recording gaps are closed by MCP-2..MCP-5.

## Architecture

Two interposition modes behind **one adapter and one record path**.

```
stdio:  harness ──launches──▶ agentwatch mcp-proxy ──spawns──▶ real server
                                   │
http:   harness ──POST/SSE──▶ loopback listener ──forwards──▶ upstream URL
                                   │
                            frame {phase:"mcp"} ─▶ daemon.sock ─▶ mcp_proxy adapter ─▶ redact ─▶ chained store
```

The proxy relays every frame **unchanged** and records **out-of-band**: recording never gates the protocol.
Records reach the store through the existing single-writer path — the proxy sends a framed message to the
daemon over the Unix socket (reusing `hook.send` + `Spool`), and the daemon normalizes it. Redaction, secret
detection, dedup, the hash chain, and the conformance runner are reused unchanged.

### Components

| Unit | Path | Responsibility |
|---|---|---|
| Adapter | `src/agentwatch/adapters/mcp_proxy.py` | JSON-RPC frame → `AgentRecord`s; strict capability/gap boundary |
| Proxy engine | `src/agentwatch/mcp_proxy.py` | stdio + HTTP/SSE relay, request/response pairing, frame emission, `main` |
| Config | `src/agentwatch/mcp_config.py` | re-point `mcpServers`, byte-exact backup, hash-guarded restore |
| Daemon route | `src/agentwatch/daemon.py` | handle `phase == "mcp"` → adapter; quarantine on normalize error |
| Protocol | `src/agentwatch/protocol.py` | add `"mcp"` to `FRAME_PHASES` (additive) |
| CLI | `src/agentwatch/cli/main.py` | `init --mcp-proxy`, `uninstall`, `mcp-proxy` subcommand |
| Packaging | `packages/python-sdk/pyproject.toml` | `agentwatch-mcp-proxy` console entry point |

## Adapter boundary contract

`agentwatch.adapters.mcp_proxy`:

- `HARNESS_ID = "mcp-proxy"`
- `CAPABILITIES = frozenset({"mcp-tools"})`
- `DOCUMENTED_GAPS = ("mcp-resources", "mcp-prompts", "mcp-sampling")`
- `class McpProxyAdapterError(ValueError)`
- `normalize(message: Mapping[str, Any], *, redaction: RedactionConfig | None = None) -> list[AgentRecord]`

### Frame shape

```json
{
  "phase": "mcp",
  "harness": "mcp-proxy",
  "event": {
    "server": "github",
    "session_id": "01J…",
    "direction": "request",
    "tool_name": "issue_get",
    "rpc": {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
            "params": {"name": "issue_get", "arguments": {"number": 3}}},
    "timestamp": "2026-10-03T12:00:00+00:00",
    "cwd": "/repo"
  }
}
```

- `server` (str, required) — the configured MCP server key; becomes `tool.server`.
- `session_id` (str, required) — env-correlated or generated (see below).
- `direction` (`"request"` | `"response"`, required).
- `tool_name` (str) — required on **response** (a JSON-RPC response does not carry the method); ignored on request.
- `call_id` (str, optional) — a proxy-assigned id unique per call; the request and its response share it.
  Used for `span_id` correlation so a reused JSON-RPC id cannot collide in the daemon's dedup key.
- `rpc` (object, required) — the verbatim JSON-RPC 2.0 message.
- `timestamp`, `cwd` optional; `cwd` maps to `project`.

### Normalization

- **Reject, never drop.** `normalize` raises `McpProxyAdapterError` unless `phase == "mcp"`, `direction` is valid,
  and the RPC is a valid `tools/call` shape. A declared gap or an unknown phase is rejected explicitly (satisfies
  the conformance runner's gap/unknown probes with the default probe).
- **Request** → intent record: `step_type=act`, `tool.name` from `params.name`, `tool.server` from `server`,
  `tool.arguments` from `params.arguments` (redacted), `outcome=ok`, no end time.
- **Response** → outcome record: `step_type=observe`, `tool.name` from `event.tool_name`, `outcome=error` when
  `rpc.error` is present else `ok`, `tool.response` from `rpc.result` (redacted), end time = event time.
- **Pairing:** `span_id = f"mcp:{server}:{call_id}"` when the proxy supplied a `call_id`, else
  `f"mcp:{server}:{rpc.id}"` when `id` is present, else `None` (request and response agree).
  `trace_id = event.trace_id or session_id`.
- **Redaction:** `redact_mapping` runs before any storage transform; default is metadata-only (no argument/result
  content) unless a `RedactionConfig` is passed, mirroring `claude_code.normalize` (DD-06). A detected secret
  emits a `SECRET_DETECTED` security event even when content is not captured (R5).

## Proxy engine

- `run_stdio(server_name: str, command: Sequence[str], *, socket_path: str | None = None, env: Mapping[str, str] | None = None) -> int`
  spawns `command` as a subprocess and relays newline-delimited JSON-RPC in both directions on two threads.
  Lines are forwarded byte-for-byte; each line is parsed only to decide whether it is a recordable `tools/call`
  request/response. On harness or server EOF the other side is closed and the child reaped.
- `serve_http(routes: Mapping[str, str], *, host: str = "127.0.0.1", port: int = 0, socket_path: str | None = None, transport: str = MCP_TRANSPORT_STREAMABLE) -> int`
  binds a loopback `ThreadingHTTPServer` serving one route per `server → upstream URL` pair. A request to
  `/<server>` is forwarded to that server's upstream with method/headers preserved (hop-by-hop headers dropped,
  `Host` rewritten; `Authorization`/OAuth untouched); the response is streamed back and parsed for a JSON-RPC
  reply to record. GET SSE streams are proxied verbatim. An unknown route returns 404.
  - **Transport (`MCP_TRANSPORT_STREAMABLE`, default, 2026-07-28).** The proxy is **stateless** — sessions are
    removed by the spec, so it neither requires, forwards, nor emits `Mcp-Session-Id` in either direction, and
    `MCP-Protocol-Version` is relayed unchanged. Single-endpoint POST (JSON or SSE response) is the streamable shape.
  - **Transport (`MCP_TRANSPORT_HTTP_SSE`, legacy, deprecated-in-spec).** The relay is byte-verbatim, including
    `Mcp-Session-Id`, for servers still on the pre-2026 transport.
- The **`init` install mode** runs one long-lived `agentwatch mcp-proxy --http --route NAME=URL …` process;
  each harness `url` points at `http://127.0.0.1:<port>/<server>`. Default port 8765, configurable; an occupied
  port fails closed.
- `Recorder` pairs responses to requests by `rpc.id` (remembering tool name + start time) and emits frames via
  `hook.send`; a failed send is spooled, never blocks.
- `resolve_session_id(env) -> str`: `AGENTWATCH_SESSION_ID`, then `CLAUDE_SESSION_ID`, else generated
  `mcp-<12 hex>` (per process for stdio, per connection for HTTP). Correlates proxy records to the harness
  session for the WBS "cross-harness trace correlation" test.
- `main(argv: Sequence[str] | None = None) -> int` — argparse: stdio mode `--server NAME -- <command> [args…]`;
  HTTP mode `--http [--host H] [--port P] [--transport T] (--route NAME=URL)…` (`T` defaults to
  `streamable-http`).

### Error handling / fail-closed

- Malformed JSON from either side: relayed unchanged, **not** recorded, counted, never fatal (PRD 17;
  JSON-RPC framing is a fuzz target, Q3).
- Upstream/transport failure: the error is relayed to the harness and recorded with `outcome=error`.
- Daemon unreachable: the frame is spooled (`Spool`), never blocks the tool call.
- Unparseable harness config: `InstallError`, never overwritten (F7).
- Restore when the config changed after install: fail closed, warn, leave the file untouched.

## Config install / restore contract (`agentwatch.mcp_config`)

- `--scope project` → `<cwd>/.mcp.json`; `--scope user` → `~/.claude.json` top-level `mcpServers`
  (mirrors the existing hook scopes). `resolve_mcp_scope(scope, *, cwd=None, home=None) -> McpConfigTarget`.
- `install_mcp_proxy(target, *, proxy_command, servers=None) -> McpInstallReport`
  - Requires explicit consent (the `init --mcp-proxy` flag); never silent (D-P).
  - Backs up the exact original bytes to a sidecar (`<path>.agentwatch-mcp-backup`) before the first edit.
  - Writes a manifest (`<path>.agentwatch-mcp-manifest.json`) recording `created` (file did not exist),
    `written_sha256` (hash of what we wrote), and the original value of each re-pointed server.
  - Re-points **only** the servers present at install time (`servers=None` means all). Each stdio server becomes
    `{"command": <proxy executable>, "args": ["mcp-proxy","--server",NAME,"--",<orig command>,...<orig args>]}`;
    each HTTP/SSE server's `url` becomes the loopback route. `env`, `type`, and unrelated keys are preserved.
- `uninstall_mcp_proxy(target) -> McpUninstallReport`
  - If the current file's SHA-256 equals `written_sha256`, restore the backup bytes **exactly**; if the file was
    created by us, delete it; otherwise fail closed with a reason and leave the file.
  - Removes the sidecar/manifest on success. Servers added after install are untouched.
- `mcp_proxy_installed(target) -> bool`.

## Testing

- **Unit:** adapter normalize (request, response, error response, gap/unknown rejection, secret detection,
  id pairing); `resolve_session_id`; JSON-RPC framing/parse with malformed input (contained).
- **Proxy integration:** fake stdio MCP server subprocess → both directions recorded; local fake HTTP/SSE server
  → recorded; streaming and concurrent calls; error response recorded as `error`; daemon-down spooling.
- **Config:** install re-points only selected servers and preserves unrelated keys; uninstall restores bytes
  identically; created-file deletion; changed-file fail-closed; unparseable-file refusal.
- **Conformance:** `mcp_proxy` spec registered in `tests/conformance_registry.py`, fixtures under
  `tests/fixtures/mcp-proxy/`, and the pack check passes.
- **CLI:** `init --mcp-proxy` (dry-run + apply), `uninstall` reverses, `mcp-proxy` command round-trip.
- **Gates:** all tests pass; coverage ≥ 95%; `ruff` zero; `mypy --strict`.

## Documentation

- New: this file; link from `docs/design/README.md`.
- Update: `docs/reference/adapter-conformance.md`, `compatibility.md`, `known-limitations.md`, `cli-reference.md`,
  `daemon-protocol.md` (new `mcp` phase), `CHANGELOG.md`, WBS Part 6 + index.

## Decomposition

Delivered as **two implementation plans** (each produces working, testable software):

- **Plan A — adapter + stdio proxy + daemon routing + conformance.** Records `tools/call` both directions
  end-to-end through the daemon; the `agentwatch mcp-proxy` command is invoked manually. Independently shippable.
- **Plan B — HTTP/SSE proxy + `init --mcp-proxy` install/restore.** The headline acceptance: re-points config,
  records HTTP/SSE traffic, and restores the config byte-for-byte.

## Resolved decisions

| # | Decision |
|---|---|
| D-M1 | Interpose on **both** stdio and HTTP/SSE MCP transports (user-elected scope). |
| D-M2 | Record **`tools/call` only**; resources/prompts/sampling are relayed but declared gaps. |
| D-M3 | Correlate records to the harness session via `AGENTWATCH_SESSION_ID` / `CLAUDE_SESSION_ID`; else a generated `mcp-*` session. |
| D-M4 | Manage **`.mcp.json` (project)** and **`~/.claude.json` (user)**; byte-exact backup + hash-guarded restore. |
| D-M5 | Records reach the store via the **daemon socket** with a new `mcp` phase, reusing the single-writer path. |
| D-M6 | One long-lived HTTP proxy process with a route manifest; default loopback port 8765, fail closed if taken. |
| D-M7 | **Streamable HTTP is the default transport** (2026-07-28, stateless: `Mcp-Session-Id` is neither required, forwarded, nor emitted); `--transport http-sse` keeps the legacy relay verbatim, **deprecated-in-spec** (M27 MCP-1, ADR-0023). |
