# PRD 42 — Harness Fidelity & Real-Time

**BLUF:** Kill the "modeled" rows honestly and make the record live: **Cursor** via its native hooks,
**Gemini CLI** via its built-in OTel telemetry, **Codex** via its documented rollout logs, the **MCP** proxy
brought up to the 2026-07-28 spec (Streamable HTTP; the deprecated surfaces marked closed-by-spec), a
**streaming** daemon with live operator views, and **LangGraph/raw-Python** Tier-2 at full fidelity.

**Status:** proposed v0.2.0 (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M25–M27 ·
**M25 subset implemented:** CUR-1/CUR-2, GEM-1, STR-1 (COD/MCP/LG/STR-2/3 in later milestones).
**Depends on:** PRD 25, PRD 27, PRD 36 · **Extends:** PRD 27 (Harness Expansion)

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only,
> every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency
> without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

Through-line from PRD 27: **depth before breadth, then expand at the cheapest fidelity per adapter** — native
hooks → interposition → ingest → log-read. v0.2.0 proves the 2026-10-05 feasibility finding that Cursor, Codex,
and Gemini can all leave "modeled" largely through the two horizontals (hooks + ingest), not bespoke work.

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| CUR-1..3 | Cursor recorded via native hooks (full loop incl. file reads/reasoning) | "modeled" is the released credibility gap; Cursor hooks proven at 13M events/1,100 machines | CUJ-1 (Cursor) |
| GEM-1..2 | Gemini CLI recorded via its built-in OTel telemetry | full fidelity is a settings flip, and it carries approval + principal attributes | CUJ-1 (Gemini), CUJ-14 |
| COD-1 | Codex recorded from documented rollout logs | cheapest honest fidelity for the 2nd-most-used Tier-1 CLI | CUJ-1 (Codex) |
| MCP-1..6 | Full MCP surface (resources/prompts/elicitation/tasks) on Streamable HTTP | spec moved (2026-07-28); resources/prompts are the exfiltration/injection surfaces | CUJ-13 |
| STR-1..3 | Streaming daemon + live views | G1: batch (~30 s) is the most visible limitation; SOC consumers expect streams | CUJ-17 |
| LG-1..2 | LangGraph / raw-Python Tier-2 at full fidelity | matrix earmark; completes the "one install, one format" embedder story | CUJ-11 |

**The "how" lives in design docs:** per-harness capture mechanics in
[`design/harness-adapter-design.md`](../design/harness-adapter-design.md) (Cursor/Gemini/Codex sections); the MCP
protocol posture in [`design/mcp-surface.md`](../design/mcp-surface.md); streaming in
[`design/streaming-views.md`](../design/streaming-views.md).

### CUR-1..3. Cursor full-fidelity via native hooks · v0.2.0 · (new)

**Why.** The generated compatibility matrix promises Cursor for v0.1.x/v0.2.0; "modeled" rows are the released
credibility gap. Cursor ships `hooks.json` (project `.cursor/hooks.json`, user `~/.cursor/hooks.json`, org-level)
invoking external programs with JSON on stdin across the full agent loop — and Elastic Security Labs proved the
deployment at scale (13M tool-call events from 1,100 machines with one script since May 2026). Native hooks give
*new* fidelity we lack: `beforeReadFile` (file reads) and `afterAgentThought` (reasoning).

**Behavior.** **CUR-1** authenticated capture run → scrub → commit version-tagged golden fixtures (PRD 27 I2).
**CUR-2** real Cursor hooks adapter (sessionStart/End, pre/postToolUse(+Failure), shell, MCP, beforeReadFile,
afterFileEdit, subagentStart/Stop, beforeSubmitPrompt, preCompact, afterAgentThought/Response, Tab hooks
`beforeTabFileRead`/`afterTabFileEdit`, app-lifecycle `workspaceOpen`); **blocking-event
payloads are recorded as observations, never answered** (monitor-only, R2); IDE/CLI/remote tagged via env
(`VSCODE_*`, `CURSOR_CODE_REMOTE`); org-level install via the system-wide `hooks.json` is supported but stays
consent-first (D-P). **CUR-3** coverage reconciliation vs transcripts where ground truth exists.

**Data & schema impact.** Reuses the hook→daemon→store path; adds `ide` provenance and read/reasoning step types.

**Security & privacy.** Consent-first install + byte-identical restore (D-P); redaction unchanged.

**Edge cases.** Cloud agents (cursor.com/agents) lack sessionStart/beforeSubmitPrompt/Tab/workspace hooks → a
declared matrix gap, not a silent one; a blocking event we do not answer must not stall the agent.

**Dependencies.** PRD 27 (I2, O1, N4), PRD 47 (testkit), M3 hook/daemon path.

**Testing.** Golden-corpus replay green; conformance pack registered (O1); a fixture with no sessionStart still
ends cleanly.

**Risks & mitigations.** Cursor hook surface evolves fast → version-tagged corpus + nightly drift (N4).

**Decision.** ADR-0021 — native-hooks contract + monitor-only blocking-event posture + cloud-agent gaps.

### GEM-1..2. Gemini CLI via built-in OTel telemetry · v0.2.0 · (new)

**Why.** Gemini CLI ships OpenTelemetry natively (`.gemini/settings.json` `telemetry` block; OTLP gRPC/HTTP;
common attributes `session.id`, `installation.id`, `active_approval_mode`, `user.email`). Full fidelity is a
settings flip + ingest, not an adapter (S–M), and it carries approval + principal attributes we would otherwise
infer — directly feeding PRD 44 identity.

**Behavior.** **GEM-1** recipe: point `telemetry.otlpEndpoint` at our collector or `outfile` →
`ingest --format otel`; **mandatory** redaction (logPrompts defaults true). **GEM-2** map
`active_approval_mode` → approval provenance (S14); `user.email` → principal (hashed in metadata-only);
`installation.id`/`session.id` → identity.

**Data & schema impact.** Uses the OTel ingest path (PRD 41 OTEL-3); no new adapter.

**Security & privacy.** `logPrompts: true` default → the privacy pipeline is mandatory on this path; principal
hashing by default (DD-06).

**Edge cases.** Telemetry disabled by default → docs state enabling it; target `gcp` vs `local` documented.

**Dependencies.** PRD 41 (OTEL-3), PRD 27 (N2), PRD 44 (IDN).

**Testing.** A captured telemetry file ingests to validated records; the approval/principal mapping is fixture-
tested; redaction runs on the logPrompts path.

**Risks & mitigations.** Attribute drift → version-pinned fixtures + drift job.

**Decision.** ADR-0022 — settings recipe vs adapter; attribute mapping; logPrompts privacy posture.

### COD-1. Codex CLI via documented rollout logs · v0.2.0 · (new)

**Why.** Codex stores sessions as JSONL rollouts at `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`
(`session_meta`/`turn_context`/`response_item`/`event_msg`/`compacted`/plan/diff), documented and verified by
multiple independent OSS parsers; `CODEX_HOME` (and `CODEX_SESSIONS_DIR`) are overridable for testing. It is richer
than a plain transcript (per-turn model/sandbox/tool surface, plan updates, compaction with rollback semantics,
`custom_tool_call` fileChange diffs + commandExecution exit codes, token counters).

**Behavior.** A Codex reader (`agentwatch ingest --agent codex --path …`) with dedup (plaintext appears in multiple
places; F2), `.jsonl.zst` support, and a `crashed/inferred` end-state for dangling sessions (S33; ~2-min silence).

**Data & schema impact.** `producer: import` + `source: log-read`; reuses compaction/plan step types (S15/S16).

**Security & privacy.** **Untrusted-data rule (ADR-0024):** session logs are attacker-influenced; never execute,
never pass a log path to a shell (the Codex #36937 HOME-deletion incident); redaction + B4 quarantine mandatory.

**Edge cases.** Dangling session → `crashed/inferred`; duplicated message → deduped; unknown top-level type →
skipped for forward-compat.

**Dependencies.** PRD 47 (XHT-3 cross-validation), S33, B4.

**Testing.** Fixture-verified against the published format; cross-parsed against two independent OSS parsers
(XHT-3); a weaponized fixture (backtick command-substitution) is contained, never executed.

**Risks & mitigations.** Format changes per release → version-tagged fixtures + drift job.

**Decision.** ADR-0024 (shared) — foreign-data threat posture.

### MCP-1..6. MCP proxy to the 2026-07-28 spec · v0.2.0 · (new)

**Why.** The MCP spec revised (2026-07-28): **sessions removed** from Streamable HTTP; **Roots/Sampling/Logging
deprecated** (SEP-2577); **MRTR** reworks server-initiated requests; **Tasks** added; **HTTP+SSE deprecated**.
Our proxy speaks the deprecated transport and records only `tools/call` — resources/prompts are the exfiltration
and injection surfaces.

**Behavior.** **MCP-1** add Streamable HTTP (HTTP/SSE kept for legacy, marked deprecated-in-spec). **MCP-2** record
`resources/read` (+ resource links in tool results). **MCP-3** record `prompts/get`. **MCP-4** record elicitation
request/response, linked to approval provenance. **MCP-5** record tasks lifecycle; mark
sampling/roots/logging as **closed-by-spec** (SEP-2577) in known-limitations. **MCP-6** protocol-version
conformance matrix (2025-06-18 / 2025-11-25 / 2026-07-28) in N4.

**Data & schema impact.** New proxy surfaces reuse the redaction/chain/attribution pipeline; `phase: "mcp"` extended.

**Security & privacy.** Consent-first + byte-identical restore (D-P); bounded buffers; unknown methods → quarantine
+ harness-drift (S19).

**Edge cases.** Unbounded SSE streams → bounded/data-frames-only with the limit declared; unknown method →
quarantined with a reason.

**Dependencies.** PRD 27 (N1), PRD 47 (testkit), S14, S19, B4.

**Testing.** Per-surface fixtures replay green across all three protocol revisions; sampling gap documented citing
SEP-2577; malformed frames contained.

**Risks & mitigations.** Spec churn → protocol-version fixtures + drift; breaking a user's MCP setup → restore test.

**Decision.** ADR-0023 — Streamable HTTP migration + closed-by-spec gaps + protocol-version matrix.

### STR-1..3. Streaming ingestion + live operator views · v0.2.0 · (new)

**Why.** G1: batch polling (~30 s) is the most visible released limitation; every 2026 platform streams; SOC
consumers expect streamable telemetry. Real-time triage is a core operator CUJ.

**Behavior.** **STR-1** daemon→API/UI push (UDS/WS); the hook→daemon→store path stays append-then-verify (streams
*views*, not truth). **STR-2** `agentwatch tail -f` + live timeline + live anomaly inbox; back-fill reconciliation;
`degraded` on backpressure (S10). **STR-3** soak job with a streaming consumer.

**Data & schema impact.** No store change; new view path + reconciliation.

**Security & privacy.** Local UDS by default; no new egress (R6).

**Edge cases.** Consumer crash → no store loss, back-fill reconciles, gaps classified (S2); reordering → derived
views never diverge from the chain.

**Dependencies.** S10 pattern, S2, PRD 46 (API/OpenAPI), soak (M12).

**Testing.** p99 hook→view ≤ 1 s (perf gate); 24 h streaming soak; drop-consumer test.

**Risks & mitigations.** Silent gaps → append-then-verify + classified reconciliation.

**Decision.** ADR-0018 — streams are derived views; reconciliation contract.

### LG-1..2. LangGraph + raw-Python Tier-2 at full fidelity · v0.2.0 · (new)

**Why.** The compatibility matrix earmarks LangGraph + raw Python for v0.2.0; LangGraph is the most-deployed
agent framework. Completes CUJ-11 (embedder) and "one install, one format."

**Behavior.** **LG-1** `TracedGraph` auto-instrumentation emitting native records. **LG-2** raw-Python SDK path to
the unified store (or local collector). Both registered in the O1 conformance runner with an SDK conformance pack.

**Data & schema impact.** `source: sdk`; integrity distinction preserved (S11).

**Security & privacy.** Same redaction/chain; no egress.

**Edge cases.** Framework version drift → version-tagged fixtures; SDK not installed → no-op capture path.

**Dependencies.** PRD 46 (SDK-1..3), PRD 41 (PG-3), O1.

**Testing.** One command instruments a LangGraph app; spans land chain-protected; conformance pack green.

**Risks & mitigations.** SDK lifecycle loss (M14) → PRD 46 flush/shutdown guarantees.

**Decision.** Covered by PRD 46 SDK ADRs.
