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

> **B1:** v0.1.0 is Claude Code only (meta-MVP); the ecosystem ≥2-Tier-1 threshold is met by v0.3.0.
>
> **Provisional (M10, modeled):** Cursor, Codex CLI, and Gemini CLI also ship **provisional** adapters in
> v0.1.0 — their native event shapes are assumed, not captured, so the roadmap placement above still governs
> *full-fidelity* support. Replace the modeled fixtures with real captures (M14/N4) before treating them as
> mature.
>
> Claude Code recording via `PreToolUse`/`PostToolUse` hooks + the local daemon is implemented in M3
> (see the [hook contract](../design/claude-code-hook-contract.md)); declared gaps apply.
