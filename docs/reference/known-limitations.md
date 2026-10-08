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
- **Capability inventory (`CAP-1`, M30) covers Claude Code today.** `agentwatch inventory --capabilities` reads
  skills, plugins, hooks, subagents, commands, rules files and MCP servers under `~/.claude` / `<project>/.claude`
  (plus best-effort managed paths) by **content digest**; Cursor, Codex CLI and Gemini CLI are declared `none` in the
  per-harness coverage matrix, and memory is `none` for every harness pending `MEM-1`. `bom --format cyclonedx`
  includes the discovered capabilities. (proving test:
  `packages/python-sdk/tests/test_capabilities.py::test_coverage_declares_per_harness_gaps`).
- **Capability snapshots (`CAP-2`, M30) are recorded on demand, not yet automatically.** Drift needs a baseline: a
  `capability-snapshot` carrier is written by `inventory --capabilities --snapshot` (or `record_capability_snapshot`
  from an integrator). No session-start hook records one yet, so drift is only visible between snapshots that were
  actually taken. (proving test:
  `packages/python-sdk/tests/test_capability_drift.py::test_cli_capabilities_snapshot_then_diff`).
- **Capability-load attribution (`CAP-3`, M30) has no automatic load signal yet.** No harness emits a
  "what was loaded" event in its hook payload here: Claude Code is `partial` (loads are recorded through the
  `capability-loaded` API by an integrator) and Cursor/Codex CLI/Gemini CLI are `none` in the published
  load-exposure matrix. `replay`/`impact`/`search --capability` therefore show the loads that were recorded, not
  every load a harness performed. (proving test:
  `packages/python-sdk/tests/test_capability_attribution.py::test_exposure_matrix_is_published_and_honest`).
- **Memory-store coverage (`MEM-1`, M30) is Claude Code `partial`.** Memory stores are discovered under
  `~/.claude/memory` / `<project>/.claude/memory` and changes are attributed to the session that recorded a matching
  memory write; the harness's exact auto-memory layout is not pinned, and Cursor/Codex CLI/Gemini CLI are `none` in
  the published memory-exposure matrix. Writer attribution is by key/name match, so a write recorded with an
  unrelated key leaves the change `unattributed`. (proving test:
  `packages/python-sdk/tests/test_memory_capability.py::test_out_of_band_edit_is_flagged_unattributed`).
- **Environment fingerprint (`ENV-1`, M30) components can be `unknown`.** The fingerprint is derived from what the
  record holds: if a session never recorded a capability snapshot, an MCP surface, or a recorder attestation, that
  component is the literal `unknown` rather than a guess — so two sessions can share a digest because the same facts
  were absent, not because the environments were proven identical. `drift` reports environment changes as
  "coincides with", never a cause. (proving test:
  `packages/python-sdk/tests/test_environment_fingerprint.py::test_absent_facts_are_unknown_never_inferred`).
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

## Policy

A limitation enters this file when it is discovered and leaves it only when a test proves it closed.
