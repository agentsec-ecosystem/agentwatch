# Reference — Known Limitations

**BLUF:** Honest gaps, including those inherited from the shipped project. Published, not hidden.

Status: living.

## Inherited from `agent-exec-trace` (shipped)

- Batch polling only (~30 s ingestion delay), not streaming.
- No distributed trace correlation across services.
- No multi-tenant isolation.
- LLM detectors were research-grade (10-trace sample).
- 28/35 detectors silent on the HF field-test corpus (structurally dependent on tool-use semantics).
- No PydanticAI adapter; no policy-overlay view; no memory-audit UI.

## agentwatch-specific (v0.1.0)

- Claude Code only; Cursor/Codex/Gemini not yet supported.
- Hash chain is detect-only (no signing key) at v0.1.0.
- Security-event schema v1 is draft; naming may move upstream to OTel (DD-14).

## Policy

A limitation enters this file when it is discovered and leaves it only when a test proves it closed.
