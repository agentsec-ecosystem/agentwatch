# Reference — Compatibility Matrix

**BLUF:** The honest harness × version matrix. Coverage is declared, not implied.

| Harness | v0.1.0 | v0.1.x | v0.2.0 | v0.3.0 / v1.0 |
|---|---|---|---|---|
| Claude Code | ✅ | ✅ | ✅ | ✅ |
| Cursor | — | ✅ (proxy where needed) | ✅ | ✅ |
| Codex CLI | — | — | — | ✅ |
| Gemini CLI | — | — | — | ✅ |
| GitHub Copilot (agent) | — | — | — | lower-layer/OTel |
| LangGraph (Tier-2) | — | — | ✅ | ✅ |
| raw Python (Tier-2) | — | — | ✅ | ✅ |
| CrewAI / PydanticAI | — | — | — | ✅ |
| MCP-speaking harness (via `agentwatch mcp-proxy`) | ✅ stdio + HTTP/SSE (`tools/call`) | ✅ | ✅ | ✅ |

> **MCP proxy (M10 N1):** any harness that speaks MCP can be recorded without a native adapter. v0.1.0
> records `tools/call` over **stdio and HTTP/SSE** with `tool.server` attribution, and `agentwatch init
> --mcp-proxy` re-points the harness config at the proxy (`uninstall` restores it byte-identically).
> **v0.2.0 MCP-1..6** moves the HTTP proxy to the **Streamable HTTP** transport (2026-07-28, stateless —
> sessions removed) and records the full surface (`resources/read` + links, `prompts/get`, elicitation,
> `tasks/*`); the legacy HTTP/SSE relay is kept (`--transport http-sse`) and marked deprecated-in-spec.
> The generated row carries a **Protocol** column; the proxy's tested range tracks the newest revision.
>
> **A2A proxy (M29 A2A-1/2):** `agentwatch a2a-proxy` records agent↔agent traffic (A2A v1.0): `message/send`,
> `message/stream`, `tasks/get`, `tasks/cancel` (intent → outcome), task artifacts, and agent-card exchanges over
> stdio and HTTP. Signed agent cards are verified deterministically (`verified`/`unverified`, never assumed, never an
> authorization) and a cross-org hand-off is recorded as an `agent-delegation` observation extending `tree`/`trace`.
> Consent-first `a2aAgents` install restores the file byte-identically. `tasks/resubscribe` and the
> push-notification-config family are declared gaps.
>
> **Windows (M27 WIN-1):** agentwatch supervises the daemon at logon via a **Task Scheduler** task
> (`agentwatch init --service` → `%APPDATA%\agentwatch\agentwatch-task.xml`); a `windows-latest` CI leg
> (`.github/workflows/windows.yml`) exercises the platform-independent SDK subset. Named-pipe transport and an
> end-to-end CUJ-1 timing run on Windows are tracked on WIN-1.
>
> **Managed policy (M29 DEP-1/EXT-7):** the generated table carries a **Managed policy** column
> (`effective` / `blocked` / `unknown` / `n/a`). A normal Claude Code user/project install is **blocked** under
> `allowManagedHooksOnly`; agentwatch ships a managed hook / force-enabled org-plugin path so it can still run
> (`docs/design/managed-policy-install.md`). Framework rows (ADK / Strands / OpenAI Agents SDK / Claude Agent SDK)
> are a **generator input that WS-D (FWK-1) populates** — they are not shipped adapters.

> **B1:** v0.1.0 is Claude Code only (meta-MVP); the ecosystem ≥2-Tier-1 threshold is met by v0.3.0.
>
> **Provisional (M10, modeled):** Cursor, Codex CLI, and Gemini CLI also ship **provisional** adapters in
> v0.1.0 — their native event shapes are assumed, not captured, so the roadmap placement above still governs
> *full-fidelity* support. Replace the modeled fixtures with real captures (M14/N4) before treating them as
> mature.
>
> Claude Code recording via `PreToolUse`/`PostToolUse` hooks + the local daemon is implemented in M3
> (see the [hook contract](../design/claude-code-hook-contract.md)); declared gaps apply.

<!-- BEGIN GENERATED HARNESS MATRIX -->
| Harness | Tier | Tested range | Protocol | Fidelity | Managed policy | Invocation | Notes |
|---|---|---|---|---|---|---|---|
| `adk` | Tier-2 | 1.5.0–1.x | — | modeled | n/a | OTel GenAI over OTLP (`agentwatch ingest --format otel`) | Google ADK native spans; fixture-driven, live run BLOCKED (not installable here) |
| `claude-agent-sdk` | Tier-2 | 0.1.0–0.x | — | modeled | n/a | shared Claude Code OTel (`ingest --format claude-otel`, `sdk-native`) | Routes through 29.CCO-1 (WS-A); tool_use_id join owned by CCO-1, live run BLOCKED |
| `claude-code` | Tier-1 | 2.0–2.x | — | live-verified | blocked | native hooks (`agentwatch init`) | PreToolUse/PostToolUse + local daemon; under `allowManagedHooksOnly` a user/project install is blocked — managed hook/plugin path (DEP-1) |
| `codex-cli` | Tier-1 | 0.65–0.x | — | fixture-verified | n/a | log-reader (`ingest --agent codex`) | rollout JSONL / .jsonl.zst; format-derived + cross-parser validated (COD-1/XHT-3); live capture pending |
| `crewai` | Tier-2 | modeled | — | modeled | n/a | native adapter (modeled) |  |
| `cursor` | Tier-1 | 1.7–1.x | — | fixture-verified | unknown | native hooks (`hooks.json`) | full loop; vendor+MIT fixture corpus (25.CUR-1); live capture pending |
| `gemini-cli` | Tier-1 | modeled | — | modeled | n/a | native OTel telemetry (`ingest --format otel`) | native approval/principal mapping (GEM-2); live capture pending |
| `mcp-proxy` | proxy | 2026-07-28 | 2026-07-28 | live-verified | n/a | `agentwatch mcp-proxy` / `init --mcp-proxy` | MCP JSON-RPC full surface (tools/resources/prompts/elicitation/tasks), Streamable HTTP |
| `openai-agents` | Tier-2 | 0.1.0–0.x | — | modeled | n/a | OpenInference → OTLP (`agentwatch ingest --format otel`) | OpenAI Agents SDK via OpenInference; fixture-driven, live run BLOCKED (not installable here) |
| `pydantic-ai` | Tier-2 | modeled | — | modeled | n/a | native adapter (modeled) |  |
| `strands` | Tier-2 | 1.0.0–1.x | — | modeled | n/a | OTel GenAI over OTLP (`agentwatch ingest --format otel`) | Strands native spans; fixture-driven, live run BLOCKED (not installable here) |
<!-- END GENERATED HARNESS MATRIX -->

