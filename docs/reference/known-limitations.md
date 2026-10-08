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
- ~~No memory-audit.~~ **Closed in M28 (DET-7):** memory read/write/delete are recorded (metadata always;
  content gated by privacy mode) and filterable with `agentwatch search --memory` (proving test:
  `packages/python-sdk/tests/test_memory_surface.py`). A dedicated memory-audit **UI** is still absent.
- No PydanticAI adapter; no policy-overlay view.
- **Phased to v0.2.x (M28 cut-line, declared not dropped):** the derived Postgres query tier (`PG-1..3` →
  M30, re-sequenced behind the embedded index `LUI-2`), a system-effects ingest (`SYS-1`), and an ACS
  Guardian ingest (`ACS-1`) → M29 (need external specs/captures). **A2A interposition + signed-card
  provenance (`A2A-1/2`) shipped in M29** (`agentwatch a2a-proxy`; see below).
  M30, re-sequenced behind the embedded index `LUI-2`), and A2A interposition/provenance (`A2A-1/2`) → M29
  (need external specs/captures). *(Landed in M29: a system-effects ingest (`SYS-1`) and an ACS Guardian
  ingest (`ACS-1`); see below.)*
- **System-effects ingest (`SYS-1`, M29) is Linux-only.** `agentwatch ingest --format system-ingest`
  reads an AgentSight/Tracee-shaped foreign stream and is **opt-in** (`--consent`); every record is labeled
  `source: system-ingest`, a lineage not owned by exactly one session is `unjoined` (never guessed), and the
  synthetic-corpus false-join precision is published (1.00/1.00). agentwatch **does not build probes**
  (Linux-root eBPF); macOS/Windows are the declared gap. `platform_covered("darwin") is False`.
- **ACS Guardian ingest (`ACS-1`, M29) is monitor-only and revision-pinned.** `agentwatch ingest --format acs`
  reads a Guardian audit trail (ACS v0.1.0 JSON-RPC) and records `deny`/`modify`/`ask`/`defer` as
  `denied`/`policy-fired` with `record_phase: pre_execution`; enforcement stays in the Guardian and agentwatch
  never executes a decision. The spec is young (watch item): signature and SessionContext-chain verification
  (the ACS Crypto/Audit profiles) are **not** done, and the emit-side spike (PRD 45 §ACS-1b) is not built.
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
- **A2A interposition** (`agentwatch a2a-proxy`, M29 A2A-1) records A2A `message/send`, `message/stream`,
  `tasks/get`, and `tasks/cancel` (intent → outcome), task artifacts, and agent-card exchanges over stdio
  and HTTP; `tasks/resubscribe` and the push-notification-config family are declared gaps (relayed, never
  silently dropped). Consent-first install re-points an A2A client's `a2aAgents` entries and `uninstall`
  restores the file byte-identically — agentwatch's interposition convention, since A2A defines no standard
  client config file. **Signed-card provenance (A2A-2):** a card's JWS signature is verified deterministically
  against a held key (local `AGENTWATCH_A2A_JWKS` or an explicit mapping); the outcome is recorded as
  `verified`/`unverified` and is **never** an authorization. Cards we cannot verify (unsigned, unknown key,
  unsupported alg) are recorded `unverified` with a reason. Canonicalization is RFC 8785-style (sorted keys,
  no whitespace); full JCS number-normalization is a declared gap. A cross-agent hand-off is recorded as an
  `agent-delegation` observation that extends `tree`/`trace` across org boundaries; it is evidence of an
  on-behalf-of hop, never a verdict.
- OTel/NDJSON ingestion (`agentwatch ingest`, M10 N2) is a **transcoder, not a general OTel backend**
  (D-Q): it maps GenAI spans/attributes onto records + security events and quarantines what does not
  normalize. OTLP JSON and newline-delimited JSON only — not OTLP/gRPC or protobuf — and a huge OTLP JSON
  document is loaded whole (NDJSON streams line-by-line).
- Compatibility/version matrix (M10 N4) fingerprints the *shape* of conformance fixtures; a field addition
  counts as drift and is surfaced for a human review, not auto-applied. Modeled adapters have no real
  version range yet ("modeled").
- Framework recipes (M29 FWK-1) are **`modeled`**, not live-verified: Google ADK, Strands Agents, the OpenAI
  Agents SDK (via OpenInference) and the Claude Agent SDK are not installable in the build sandbox, so each
  recipe ships with a shape-derived fixture + a CI O1 conformance pack and its live pinned run is marked
  **BLOCKED**. The Claude Agent SDK additionally routes through the shared Claude Code OTel ingest owned by
  **29.CCO-1 (WS-A)**; until that lands its `tool_use_id` attribute is reported in the explicit `unmapped`
  bucket rather than silently dropped.
- Hash chain is detect-only (no signing key) at v0.1.0.
- Security-event schema v1 is draft; naming may move upstream to OTel (DD-14).
- Fleet access roles are **enforced but not provisioned**: the M29 ACC-1 model (`agentwatch.access`)
  documents and enforces the role × data-class matrix and records every cross-user read, but role
  *assignment* — which human holds which role, and under a managed policy — is supplied per request
  until **29.DEP-1** (PRD 50, WS-B) lands. A wrong or missing role denies rather than silently granting
  (proving test: `packages/python-sdk/tests/test_access.py::test_cross_role_read_returns_nothing_and_is_recorded`).
- Legal holds are enforced on the **chain store** (retention skips; `purge` fails closed with a recorded
  override); propagation to *every* derived index/export artifact is **30.EXT-5** (M30, behind the embedded
  index LUI-2) and is not in this branch. A hold does not yet reach a Postgres/console tier that does not
  exist here (proving test: `packages/python-sdk/tests/test_legal_hold.py::test_retention_skips_held_records`).
- Incident cases (`agentwatch case`, M30 IR-1) reconstruct a merged timeline from **one local store**: a case
  crossing machines requires those stores to be pooled first (there is no cross-host case transport). A
  store-level tombstone cannot be attributed to a member session after the fact (its payload is dropped), so
  it is reported as a store-level `tombstone` gap and never guessed into a session. Case export is manual and
  local — there is no registry submission path (proving test:
  `packages/python-sdk/tests/test_incident_cases.py::test_timeline_classifies_time_and_explicit_gaps`).
- The offline browser verifier (M30 VFY-1, `docs/release/verifier/agentwatch-verify.html`) is **checksummed
  in-repo but signed at release time**: a private key is never committed, so the ed25519 signature over
  `SHA256SUMS` is produced by `scripts/build_browser_verifier.py --sign` in the release pipeline (proving
  test: `packages/python-sdk/tests/test_browser_verifier.py::test_checksum_matches_the_artifact_and_is_listed_in_release_evidence`).
  The differential test drives the inlined verifier core under a JS engine; a real-browser `file://` smoke run
  is part of release readiness (VFY-1), not of the unit gate. The page re-verifies the current evidence-bundle
  format only.
- Runner segments (M30 RUN-1) carry **per-import** custody: the segment's own chain proves integrity from the
  runner's genesis, but there is no continuous chain between the runner and the importing host, and redaction is
  the runner's responsibility (import refuses `privacy_mode=full` records, but cannot re-derive what the runner
  already dropped). A cross-host join is by W3C `traceparent` only; when the header is absent the runner session
  is imported **unjoined**. Proving test:
  `packages/python-sdk/tests/test_runner_segments.py::test_imported_records_are_visibly_weaker_than_local`.

## Policy

A limitation enters this file when it is discovered and leaves it only when a test proves it closed.
