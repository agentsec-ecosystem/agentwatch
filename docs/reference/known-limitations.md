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
- The static synthetic demo bundle (M30 DEMO-1, `examples/demo-bundle/`) is committed, offline and secret-scanned,
  but the **VFY-1 browser page** that renders it is **30.VFY-1** (not in this branch); opening it in the browser is
  therefore deferred while the artifact itself is complete (proving tests:
  `packages/python-sdk/tests/test_demo_bundle.py::test_bundle_makes_zero_network_references`,
  `test_bundle_is_secret_scanned_by_two_independent_scanners`).
- Recurring failure signatures (M30 OUT-2) are computed deterministically in `digest` (`SIGNATURES_VERSION = sg1`);
  the console/LUI rendering of the same patterns is **deferred to 30.LUI-1** (WS-3) and is not in this branch, so the
  browser view does not yet show them (proving test:
  `packages/python-sdk/tests/test_outcome_signatures.py::test_signature_grouping_is_deterministic_and_versioned`).
- Hash chain is detect-only (no signing key) at v0.1.0.
- Security-event schema v1 is draft; naming may move upstream to OTel (DD-14).
- Fleet access roles are **enforced but not provisioned**: the M29 ACC-1 model (`agentwatch.access`)
  documents and enforces the role × data-class matrix and records every cross-user read, but role
  *assignment* — which human holds which role, and under a managed policy — is supplied per request
  until **29.DEP-1** (PRD 50, WS-B) lands. A wrong or missing role denies rather than silently granting
  (proving test: `packages/python-sdk/tests/test_access.py::test_cross_role_read_returns_nothing_and_is_recorded`).
- Legal holds are enforced on the **chain store** (retention skips; `purge` fails closed with a recorded
  override) and **propagate to the derived index** as of **30.EXT-5** (M30): a refused purge touches nothing, a
  successful purge/retention drops the erased rows from the embedded index, and `purge`/`retention` **enumerate**
  known leftover artifacts (archives, parquet/NDJSON exports, repair-evidence copies, quarantine) rather than
  assuming them absent. A hold still does not reach a Postgres tier, which is not built here (proving tests:
  `packages/python-sdk/tests/test_legal_hold.py::test_retention_skips_held_records`,
  `packages/python-sdk/tests/test_purge_propagation.py::test_blocked_purge_does_not_touch_the_index`).
- The embedded query index (M30 LUI-2) is a **derived** convenience over the chain store: it is stdlib
  `sqlite3` with no service and no heavyweight dependency, deletable at any time. Columnar export is the one
  optional path — `export-parquet` needs the `agentwatch[parquet]` extra (`pyarrow`) and otherwise fails
  closed rather than silently degrading. Postgres is **not** the general-case tier; it remains the
  fleet/multi-tenant tier (PRD 41 PG-2, re-sequenced behind the embedded index in ADR-0035/EXT-8) and is not
  built here (proving tests: `test_query_index.py::test_import_does_not_pull_pyarrow`,
  `test_query_index.py::test_rebuild_is_bit_for_bit`).
- `agentwatch ui` (M30 LUI-1) is a **single-operator, loopback-only** console over the local chain store; it has
  no accounts, roles, or remote access (that is the fleet/Postgres tier, P7/GOV role model, PRD 56). It is
  read-only and refuses non-loopback Host headers, but it is not a hardened multi-user service (proving tests:
  `test_console.py::test_console_binds_loopback_even_when_asked_otherwise`,
  `test_console.py::test_console_rejects_a_non_loopback_host_header`).
- The agent-facing MCP server (`agentwatch mcp-serve`, **30.AGI-1**) is **read-only and off by default**
  (`--enable`); it exposes no mutating tool and cannot enforce or block. Its responses are labeled
  `untrusted-data` with record citations and every query is recorded as a metadata-only `store-access`
  record; a client that ignores the label still receives no instruction channel. Injection-shaped record
  content cannot change behavior (proving test:
  `packages/python-sdk/tests/test_mcp_server.py::test_injection_shaped_record_content_does_not_change_behavior`).
- The versioned CLI JSON contract (**30.AGI-2**) covers a documented **read/investigation subset** of
  commands (`schema/cli/v0.1.0/`, see `agentwatch.cli_schema.READ_COMMANDS`), not every command that emits
  `--json`; more join additively under the changelog guard. The HTTP contract is PRD 46 API-1 and is not
  built here (proving test: `packages/python-sdk/tests/test_agent_interfaces.py`).
- `suggest-policy` (**30.POL-1**) is **advisory only**: it never edits harness settings, never enforces, and
  writes nothing outside `--out`. Its quality is bounded by captured arguments — a metadata-only call that
  cannot be command-scoped becomes an explicit coverage gap, never a guessed rule. The `acs` target is a thin
  consumer of the ACS audit shape (PRD 45); the emit-side ACS depth is not built (proving test:
  `packages/python-sdk/tests/test_policy_suggest.py::test_cli_writes_only_the_out_file`).
- `what-if` (**30.POL-2**) is a **labeled simulation**, not a predictor: it replays a policy over *recorded* calls
  only. Matcher matching is best-effort (`Tool` / `Tool(program:*)`); unsupported syntax is reported and ignored,
  and unmatched calls default to `ask`. It cannot foresee calls the recorder never saw (proving test:
  `packages/python-sdk/tests/test_policy_whatif.py::test_report_is_labeled_simulation_and_stamped`).
- **Code provenance (M30 PRV) — declared gaps.** Range+hash capture (PRV-3) is implemented as a content-free
  primitive (`agentwatch.provenance.capture_ranges`; ranges + keyed hashes, never content) that is legal under
  `metadata-only`; persisting the reserved fact from the live hook **before** redaction belongs to the
  record/redaction path (a different workstream), so end-to-end persistence under `metadata-only` is not in this
  branch (proving test:
  `packages/python-sdk/tests/test_code_provenance.py::test_capture_is_content_free_under_metadata_only`).
  Harnesses that do not expose a line range fall back to file-level `heuristic` attribution, never a guessed
  range. Line tracking across rebase/squash (git-ai's domain) is out of scope.
- **Agent Trace (M30 PRV-2) — declared gaps.** The export pins `agent-trace-rfc-0.1` rather than claiming
  conformance to a stable standard; the live upstream revision is not fetched in the build sandbox, so the pin is
  checked against a committed snapshot (`schema/agent-trace/upstream-revision.json`). PR targets resolve **offline**
  by matching a merge/squash subject `(#N)` — a repository with a nonstandard merge-message format may not resolve.
  Cross-validation is diagnostic (agree/disagree/agentwatch-only/notes-only); agentwatch never rewrites existing
  git-ai notes, and writing its own notes requires the explicit `export-session --format agent-trace --write-notes`
  command (proving test:
  `packages/python-sdk/tests/test_provenance.py::test_agent_trace_default_export_writes_nothing_to_the_repo`).
- **Concurrency (M30 CNC-1) — declared gap.** `agentwatch concurrency` is a **report only**: overlaps are derived
  from recorded `started_at`/`ended_at` intervals (a session that never sets `ended_at` collapses to a point) and
  shared-file edits from classified file-modification targets; it enforces nothing and the PRD asks to validate demand
  in the field before building beyond the report (proving test:
  `packages/python-sdk/tests/test_concurrency.py::test_two_session_fixture_reports_overlap_and_shared_file`).
- **Outcome facts (M30 OUT-1) — declared gap.** Outcome facts are **deterministic and non-scoring** (test/build/lint
  pass ratios, retained/reverted/interrupted/rejected counts, retries-to-success) with a derivation version
  (`out1`); there is no LLM-judged quality and no "score". Retained change requires a **local git repository** —
  without one the denominator is preserved as **unknown**, never guessed — and a session that never sets `ended_at`
  yields a point span (proving test:
  `packages/python-sdk/tests/test_outcomes.py::test_cost_per_unknown_denominator_is_none`).

## Policy

A limitation enters this file when it is discovered and leaves it only when a test proves it closed.