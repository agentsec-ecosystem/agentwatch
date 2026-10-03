# PRD 25 — Capture Fidelity & Data Model

**BLUF:** Record the whole story: tool responses, MCP server attribution, prompt-version fingerprint, resumed sessions, project filtering.

**Status:** proposed (2026-10-02) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–29): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification (PRD 14/18); monitor-only, every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

### D1. MCP server attribution + `agentwatch inventory` (pre-styles R9) · M9 · #177

**Why (evidence).** `mcp-server-events` is our second declared gap, and "what MCP servers are in
use and what did they do?" is a top security question (R9). Every MCP call already flows through
the adapter with the server encoded in the tool name (`mcp__<server>__<tool>`) — we record it and
discard the attribution. Full server-lifecycle inventory is M9; this is the available subset now.

**Behavior.** Records tag the serving MCP server. `agentwatch inventory [--session-id …]` prints a
per-server table: server, tools seen, call count, last seen, sessions. Local scope only (PRD 14:
no commercial discovery).

**Data & schema impact.** `ToolCall.server` already exists in the schema — populate it from
`mcp__` names (split on `__`, first segment after the prefix is the server). Narrow the declared
gap to "server lifecycle (connect/disconnect) not surfaced."

**Security & privacy.** Server/tool names are metadata; no arguments captured.

**Edge cases.** Plugin-scoped names (`mcp__plugin_<plugin>_<server>__<tool>`) → parse defensively,
record the raw name in evidence if ambiguous. A tool literally named `mcp__x__` (malformed) →
fall back to no server. MCP proxy (N1) will provide richer per-server data later.

**Dependencies.** Adapter (shipped); M9 inventory milestone.

**Testing.** Conformance fixture `mcp_tool.json`; inventory aggregation test across sessions;
plugin-scoped parsing test.

**Risks & mitigations.** Naming drift in MCP tool ids (fixtures tagged by harness version —
O1/N4).

**Decision.** D-19.11 (how strictly to parse scoped names).

### D2. Prompt-version fingerprint (CLAUDE.md digest) · M9 · #178

**Why (evidence).** CUJ-6 (version comparison) needs *something* to identify "same prompt,
different behavior." Claude Code provides no prompt id, so cohort comparison has a hole exactly
where prompt changes are the thing being investigated.

**Behavior.** `agent.prompt_version = sha256(concat(CLAUDE.md, .claude/rules/*.md sorted))[:16]`,
captured by the hook from `$CLAUDE_PROJECT_DIR` and carried in the framed message.

**Data & schema impact.** `agent.prompt_version` already exists (PRD 15). Hook message gains an
optional `prompt_version`. Multi-file: concatenate in sorted path order, then digest.

**Security & privacy.** A digest leaks only "did the prompt change" — the intended signal — never
content; same safety argument as `PrivacyMode.HASHED`. Document in `privacy-data-handling.md`
(D-19.12).

**Edge cases.** No CLAUDE.md → omit the field. Huge CLAUDE.md → stream-hash (no memory spike).
Binary/non-UTF8 → hash bytes. File changed mid-session → new digest from the next event (document
that it is per-event, not per-session).

**Dependencies.** Hook (shipped); A1 for session context; privacy docs.

**Testing.** Hook test: stable digest for a fixed file; absent file omits; multi-file order stable.

**Risks & mitigations.** Digest as a covert channel (it is one-way and coarse; documented).

**Decision.** D-19.12 (allow digest; document).


### I1. Capture tool responses (both directions) · M6 · #198

**Why (evidence).** We record what the agent asked for but never what it got back: the record
schema has no response field, and the adapter drops `tool_response` after checking `is_error`.
Loop/debugging detectors (M6) need output signal, and responses are where secrets surface (command
output carrying tokens), so capture must ride the same modes and masking as arguments.

**Behavior.** Under the active privacy mode, `tool.response` is stored alongside `tool.arguments`;
metadata-only stores none of it. From the agentwatch point of view this completes the transcript,
so a recorded turn shows request *and* result.

**Data & schema impact.** Additive `tool.response` field. Since v0.1.0 is not published, this
extends the 0.1.0 schema before first release rather than waiting for a major bump (D-I). Record
validator + JSON schema + contract tests updated.

**Security & privacy.** Responses are higher-risk than arguments (model-generated content,
command output). The same double gate (mode + `capture_tool_args`) governs; the secrets pipeline
masks before storage; `metadata-only` remains the default.

**Edge cases.** Very large responses → truncation cap applies. Binary/non-JSON responses →
store as a hash/metadata only. Response containing a secret → masked + `secret-detected`. Partial
Post with no `tool_response` → field omitted.

**Dependencies.** Adapter (shipped); secrets/redaction (M4, shipped); M6 detectors.

**Testing.** Adapter tests per mode; a secret in a response is masked and fires the event;
schema-contract test; detectors consume response signal.

**Risks & mitigations.** Storage growth from responses (mode default + caps; NFR-3 math in K4).
Schema change (pre-release window; D-I).

**Decision.** D-I (extend 0.1.0 now vs. 0.2.0).

### I3. Correlate resumed/forked sessions · M10 · #200

**Why (evidence).** Claude Code sessions resume and fork, and `SessionStart` says which
(`startup|resume|compact|fork`). If one logical session splits across ids, "one session replays
as one timeline" quietly breaks — exactly the silent gap this product exists to eliminate.

**Behavior.** A resumed/forked session links to its parent so replay and analytics can follow one
logical conversation across id changes.

**Data & schema impact.** Additive `parent_session_id` on the boundary record (or in
`security_event.evidence` if a field is undesirable). Replay walks the parent chain.

**Security & privacy.** None new (ids only).

**Edge cases.** Resume with no known parent (recorder installed late) → no link, noted. Fork
producing two children → both link to the same parent. Cycles (should not happen) → guard.

**Dependencies.** A1 session boundaries; replay (M5).

**Testing.** Resume fixture links child→parent; fork fixture links both children; replay follows
the chain.

**Risks & mitigations.** Id semantics drift across harness versions (O1/N4 fixtures).

**Decision.** D-19.26 (link semantics + field home).

### I4. Per-project session filtering · M10 · #201

**Why (evidence).** The store is global; a developer working in three projects gets one
undifferentiated session list. Claude Code events carry `cwd` — the exact grouping key we have
and do not expose.

**Behavior.** `sessions`/`tail`/`search` accept a project (cwd) filter; output groups by project.

**Data & schema impact.** Carry the project path on the record (e.g., `harness`-adjacent or in
evidence); or derive from the session's first event. Filtering must be exact (normalized path).

**Security & privacy.** Project paths are local metadata; no content.

**Edge cases.** Symlinks/worktrees (normalize to repo root where possible, but keep the raw path
too). cwd missing → `unknown` project. A session spanning two cwds (`cd` mid-session) → attribute
per record, not per session.

**Dependencies.** Adapter captures `cwd` (present in hook input); C2/H3 filters.

**Testing.** Two-project fixture filters correctly; cwd-missing case; worktree normalization.

**Risks & mitigations.** Path normalization surprises (test worktrees explicitly).

**Decision.** D-19.27 (normalize vs raw path).

