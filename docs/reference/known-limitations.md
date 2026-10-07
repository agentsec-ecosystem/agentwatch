# Reference — Known Limitations

**BLUF:** Honest gaps, including those inherited from the shipped project. Published, not hidden.

Status: living.

## Inherited from `agent-exec-trace` (shipped)

- ~~Batch polling only (~30 s ingestion delay), not streaming.~~ **Left in M26 (G1):** the STR-1 transport + STR-2
  store-truth back-fill (`agentwatch.live`) and the STR-3 streaming soak replace batch-only polling (proving tests:
  `tests/test_live_tail.py`, `tests/test_streaming_soak.py`). The operator live views (UI-1) are re-pointed to M30.
- ~~No distributed trace correlation across services.~~ **Left in M26 (G2):** `agentwatch trace <tid>` / `replay
  --trace` reconstruct one causal chain across hosts/sessions via `traceparent`, with clock-skew handling (proving
  test: `tests/test_trace.py`).
- No multi-tenant isolation.
- LLM detectors were research-grade (10-trace sample).
- ~~28/35 detectors silent on the HF field-test corpus.~~ **Resolved in M26 (DET-2/DET-3):** 38/38 rule detectors are
  non-silent on the field-test matrix, with generated, drift-guarded precision/recall in the catalog (proving test:
  `services/analytics/tests/test_detector_non_silent.py`).
- No PydanticAI adapter; no policy-overlay view; no memory-audit UI.
- Operator live views (UI-1) and the OpenCode live soak (XHT-2) are **re-pointed** to M30/M31 — declared, not dropped.

## agentwatch-specific (v0.1.0)

- Claude Code is fully supported (v0.1.0 M3). Cursor ships a native-hooks adapter on the published contract
  (v0.2.0 M25, CUR-2) with a version-tagged, secret-scanned, MIT/vendor-documented audit corpus
  (`tests/testkit/`, 25.CUR-1) — so the row is **`fixture-verified`**, not yet `live-verified` (that awaits a
  consented capture from a real install). **Codex CLI** now has a rollout **reader** (`ingest --agent codex`,
  M27 COD-1) validated against the published format (kvsankar/agent-history, verified from `openai/codex` source)
  and cross-parsed by XHT-3 — its row is `fixture-verified` (live capture pending). Gemini CLI and the Tier-2
  frameworks CrewAI and PydanticAI still have **provisional (modeled)** adapters — their native event shapes are
  assumed, not captured. Real fixtures for those land in later milestones (M14 field tests / N4 version matrix).
- Cursor cloud agents (cursor.com/agents) do not run the `sessionStart`/`sessionEnd`/MCP/Tab/`workspaceOpen`
  hooks; this is a declared gap (`cloud-agent-hook-events`), not a silent one.
- MCP interposition (`agentwatch mcp-proxy`, M10 N1) records `tools/call` over **stdio and Streamable HTTP**
  (2026-07-28; the legacy HTTP/SSE relay is kept via `--transport http-sse` and is deprecated-in-spec — see
  `tests/test_mcp_streamable_http.py`). The streamable transport is stateless: sessions were removed, so
  `Mcp-Session-Id` is neither required, forwarded, nor emitted.
  `agentwatch init --mcp-proxy` re-points `.mcp.json`/`~/.claude.json` and `uninstall` restores it
  byte-identically. MCP `resources/read` and resource links in tool results (MCP-2), `prompts/get` (MCP-3),
  elicitation (MCP-4, linked to approval provenance), and `tasks/*` (MCP-5) are recorded; the resource URI /
  prompt name / task id ride as metadata (`search --mcp-resource`). **Roots/Sampling/Logging are closed-by-spec
  (SEP-2577)** — the 2026-07-28 revision retired them, so they are relayed but never recorded, and are not on our
  roadmap. This retires the former `sampling` gap: it left by the standard, not by us.
  HTTP mode holds each forwarded request/response in memory (bounded by the upstream body); a truly
  unbounded SSE stream is relayed while open but only its `data:` frames are parsed.
- OTel/NDJSON ingestion (`agentwatch ingest`, M10 N2) is a **transcoder, not a general OTel backend**
  (D-Q): it maps GenAI spans/attributes onto records + security events and quarantines what does not
  normalize. OTLP JSON and newline-delimited JSON only — not OTLP/gRPC or protobuf — and a huge OTLP JSON
  document is loaded whole (NDJSON streams line-by-line).
- Compatibility/version matrix (M10 N4) fingerprints the *shape* of conformance fixtures; a field addition
  counts as drift and is surfaced for a human review, not auto-applied. Modeled adapters have no real
  version range yet ("modeled").
- Hash chain is detect-only (no signing key) at v0.1.0.
- Security-event schema v1 is draft; naming may move upstream to OTel (DD-14).

## Policy

A limitation enters this file when it is discovered and leaves it only when a test proves it closed.
