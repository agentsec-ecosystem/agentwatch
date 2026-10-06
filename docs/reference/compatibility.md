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
| Harness | Tier | Tested range | Protocol | Fidelity | Invocation | Notes |
|---|---|---|---|---|---|---|
| `claude-code` | Tier-1 | 2.0–2.x | — | live-verified | native hooks (`agentwatch init`) | PreToolUse/PostToolUse + local daemon |
| `codex-cli` | Tier-1 | modeled | — | modeled | native adapter (modeled) |  |
| `crewai` | Tier-2 | modeled | — | modeled | native adapter (modeled) |  |
| `cursor` | Tier-1 | 1.7–1.x | — | fixture-verified | native hooks (`hooks.json`) | full loop; vendor+MIT fixture corpus (25.CUR-1); live capture pending |
| `gemini-cli` | Tier-1 | modeled | — | modeled | native adapter (modeled) |  |
| `mcp-proxy` | proxy | 2026-07-28 | 2026-07-28 | live-verified | `agentwatch mcp-proxy` / `init --mcp-proxy` | MCP JSON-RPC full surface (tools/resources/prompts/elicitation/tasks), Streamable HTTP |
| `pydantic-ai` | Tier-2 | modeled | — | modeled | native adapter (modeled) |  |
<!-- END GENERATED HARNESS MATRIX -->
