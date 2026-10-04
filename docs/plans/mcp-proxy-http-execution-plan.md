# MCP Interposition Proxy — Plan B (HTTP/SSE + `init --mcp-proxy`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the MCP interposition proxy to HTTP/SSE MCP servers, and make `agentwatch init --mcp-proxy` re-point a harness's MCP server config at the proxy with a byte-exact, hash-guarded `uninstall`.

**Architecture:** A new loopback `ThreadingHTTPServer` (`serve_http`) serves one route per `server → upstream URL`, forwarding requests/responses unchanged while emitting `phase: "mcp"` frames to the daemon through the existing `Recorder`. A new `agentwatch.mcp_config` module owns `.mcp.json` (project) / `~/.claude.json` (user) re-pointing: backup sidecar + manifest + hash-guarded restore. The CLI orchestrates: install config, start the long-lived HTTP proxy, then `uninstall` stops it and restores bytes.

**Tech Stack:** Python 3.10+ stdlib (`http.server`, `http.client`, `ssl`, `hashlib`, `json`); `pytest` + `pytest-cov` (≥95%); `ruff`; `mypy --strict`.

**Spec:** [`docs/design/mcp-proxy-design.md`](../design/mcp-proxy-design.md) · WBS [Part 6](../wbs/v0.1.0/wbs-v0.1.0-part6-expansion.md) 10.N1 · PRD [27](../prd/27-harness-expansion.md#n1-mcp-client-interposition-adapter-one-adapter-n-harnesses--m10-212) · decision D-P/D-M1/D-M4/D-M6. Plan A: [`mcp-proxy-stdio-execution-plan.md`](mcp-proxy-stdio-execution-plan.md).

## Global Constraints

- Python 3.10+ stdlib only; no new runtime dependency (NFR-5).
- Fail closed, never silent (PRD 17); redaction before storage (DD-06); monitor-only (R2); local-first, no egress (R6).
- Recording is always **out-of-band**: a failed `hook.send` spools and never gates the protocol.
- Install is **consent-first** (explicit `--mcp-proxy`) and never silent (D-P); unrelated config keys are preserved.
- Restore is **byte-exact** and **hash-guarded**: if the file changed after install, fail closed and leave it.
- Coverage ≥95%, `ruff` zero, `mypy --strict` clean (NFR-11). Run package tests from `packages/python-sdk`.

## Review Focus

1. A response whose `id` was never seen (or duplicated) — relayed, **not** recorded, never crash.
2. Hop-by-hop headers dropped, `Host` rewritten, `Authorization` preserved.
3. An unknown route → `404`, never forwarded.
4. A batch (top-level JSON array) → relayed unchanged; each `tools/call` member recorded.
5. Unparseable harness config on install → `InstallError`, file untouched (F7).
6. `uninstall` after the config changed post-install → fail closed, file untouched, reason reported.
7. An occupied proxy port fails closed (D-M6), never silently binds another.

---

### Task 1: HTTP/SSE proxy engine

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/mcp_proxy.py`
- Test: `packages/python-sdk/tests/test_mcp_proxy_http.py`

**Interfaces:**
- Produces: `serve_http(routes: Mapping[str, str], *, host: str = "127.0.0.1", port: int = 0, socket_path: str | None = None) -> int`; `http_address(host: str, port: int) -> dict[str, str]` helper used by `init` to build loopback routes; `_records_from_payload(payload: Any) -> list[Mapping[str, Any]]` and an SSE line parser.
- Consumes: `Recorder` (Plan A).

- [ ] **Step 1: Write the failing tests.** Drive `serve_http` in a thread against a tiny stdlib upstream (`ThreadingHTTPServer` in the test), POST JSON-RPC, assert both directions recorded via a monkeypatched `hook.send`; assert `404` for unknown route; assert hop-by-hop headers dropped and `Authorization` preserved; assert SSE `data:` frames recorded.
- [ ] **Step 2: Run to verify they fail** (`serve_http` undefined).
- [ ] **Step 3: Implement.** `ThreadingHTTPServer` + a `BaseHTTPRequestHandler` subclass; `do_POST` reads the body, records each JSON-RPC message, forwards with `http.client` (drop `connection`, `keep-alive`, `proxy-*`, `te`, `trailer`, `transfer-encoding`, `upgrade`; rewrite `Host`; preserve `Authorization`), streams the response back, parses JSON or SSE `data:` lines for responses. `do_GET` proxies an SSE stream verbatim while parsing frames. Unknown route → `404`. `Recorder` gains no new public API; reuse `observe_from_harness`/`observe_from_server`.
- [ ] **Step 4: Run to verify they pass.**
- [ ] **Step 5: Commit** `feat(mcp): HTTP/SSE proxy records tools/call both directions (M10 N1 #212)`.

---

### Task 2: `main` HTTP mode + `--http` CLI flags

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/mcp_proxy.py`
- Modify: `packages/python-sdk/src/agentwatch/cli/main.py`
- Test: `packages/python-sdk/tests/test_cli_mcp_proxy.py`

**Interfaces:**
- Produces: `main` accepts `--http`, `--host`, `--port`, repeatable `--route NAME=URL`; parses each route (`NAME=URL`, `URL=http(s)://…`) and calls `serve_http`. CLI `mcp-proxy` subparser gains `--http/--host/--port/--route`.
- Consumes: `serve_http` (Task 1).

- [ ] **Step 1: Write the failing tests** — `--http --route echo=http://127.0.0.1:PORT` relays and records; a malformed `--route` exits `2`; `--http` with no `--route` exits `2`.
- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** the argparse surface in both `main` and the CLI subparser; dispatch HTTP mode before stdio.
- [ ] **Step 4: Run to verify they pass.**
- [ ] **Step 5: Commit** `feat(cli): agentwatch mcp-proxy --http route mode (M10 N1 #212)`.

---

### Task 3: Config install / restore module

**Files:**
- Create: `packages/python-sdk/src/agentwatch/mcp_config.py`
- Test: `packages/python-sdk/tests/test_mcp_config.py`

**Interfaces:**
- Produces:
  - `class McpConfigError(InstallError)`
  - `@dataclass(frozen=True) class McpConfigTarget: scope: str; path: Path`
  - `resolve_mcp_scope(scope: str, *, cwd: Path | None = None, home: Path | None = None) -> McpConfigTarget`
  - `@dataclass class McpInstallReport: target; created; repointed: tuple[str, ...]; http_routes: dict[str, str]; skipped: tuple[str, ...]; backup_path: Path; manifest_path: Path; port: int`
  - `install_mcp_proxy(target, *, proxy_command: McpProxyCommand, port: int, servers: Sequence[str] | None = None, http_host: str = "127.0.0.1") -> McpInstallReport`
  - `@dataclass class McpUninstallReport: restored; deleted; repointed_removed: tuple[str, ...]; reason: str | None`
  - `uninstall_mcp_proxy(target) -> McpUninstallReport`
  - `mcp_proxy_installed(target) -> bool`
  - `resolve_mcp_proxy_command() -> McpProxyCommand` (sibling `agentwatch-mcp-proxy` → PATH → `python -m agentwatch.mcp_proxy`).
- Consumes: `InstallError` (`agentwatch.install`).

- [ ] **Step 1: Write the failing tests** — re-points only selected stdio/HTTP servers; preserves `env`/`type`/unrelated keys; backs up exact bytes; uninstall restores bytes identically; created-file deletion; changed-file fail-closed; unparseable-file refusal.
- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** the module per the design contract (§Config install / restore).
- [ ] **Step 4: Run to verify they pass.**
- [ ] **Step 5: Commit** `feat(mcp): config install/restore with byte-exact backup (M10 N1 #212)`.

---

### Task 4: `init --mcp-proxy` + `uninstall` integration

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/install.py` (background proxy process: `start_mcp_proxy`, `stop_mcp_proxy`, `mcp_proxy_pid_path`)
- Modify: `packages/python-sdk/src/agentwatch/cli/main.py`
- Test: `packages/python-sdk/tests/test_cli_init_mcp_proxy.py`

**Interfaces:**
- Produces: `init --mcp-proxy [--mcp-scope project|user] [--mcp-servers A,B] [--mcp-port N]`; `uninstall` stops the proxy and restores MCP config before/after hook removal.
- Consumes: Task 1–3.

- [ ] **Step 1: Write the failing tests** — `init --mcp-proxy --dry-run` prints the plan and writes nothing; apply re-points `.mcp.json` and starts the proxy (pid file written); `uninstall` restores bytes and stops the proxy; a parse error exits `1` and leaves the file.
- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** the flags, orchestration, and background process lifecycle (fail closed on an occupied port).
- [ ] **Step 4: Run to verify they pass.**
- [ ] **Step 5: Commit** `feat(cli): init --mcp-proxy install + uninstall restore (M10 N1 #212)`.

---

### Task 5: Docs + full verification

**Files:**
- Modify: `docs/reference/known-limitations.md`, `compatibility.md`, `adapter-conformance.md`, `cli-reference.md`, `docs/design/mcp-proxy-design.md` (status → accepted)
- Modify: `docs/wbs/v0.1.0/wbs-v0.1.0-part6-expansion.md`, `docs/wbs/v0.1.0/wbs-v0.1.0-index.md`, `docs/plans/README.md`, `CHANGELOG.md`

- [ ] **Step 1: Update the docs** (mark 10.N1 complete; move HTTP/SSE + `init --mcp-proxy` out of known limitations).
- [ ] **Step 2: Full package gate** `python -m pytest --cov --cov-report=term --cov-fail-under=95`.
- [ ] **Step 3: Lint/type** `ruff check . && mypy --strict .`.
- [ ] **Step 4: Repo guard** `python -m pytest tests` (docs link-check, namespace guard).
- [ ] **Step 5: Commit** `docs(m10): record MCP proxy Plan B — 10.N1 complete (#212)`.
