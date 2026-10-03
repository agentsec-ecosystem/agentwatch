# PRD 19 — Agent Lifecycle Coverage

**BLUF:** Record the full Claude Code lifecycle: session boundaries, denied tool calls, prompts as reason steps, subagent attribution.

**Status:** proposed (2026-10-02) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–29): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification (PRD 14/18); monitor-only, every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

### A1. Record session boundaries (`SessionStart` / `SessionEnd`) · M5 · #165

**Why (evidence).** Today a session is only an id that appears in records; nothing opens or
closes it. Consequences: replay cannot bracket a session; an interrupted session is
indistinguishable from a completed one; our own `adapters/claude_code.py::DOCUMENTED_GAPS`
lists `session-boundaries`. PRD 15 promises "a session … closes on an explicit boundary"; PRD 17
promises gaps are "events, never absences." Claude Code now fires `SessionStart` (matcher:
`startup|resume|clear|compact|fork`) and `SessionEnd` (matcher:
`clear|resume|logout|prompt_input_exit|other`).

**Behavior.** Every recorded session has a visible start and end record. `sessions` can show
"complete" vs "interrupted"; replay starts and ends at the boundaries; F10 partial-session
closing becomes explicit.

**Data & schema impact.** No envelope or schema change. Boundary records:
`tool.name="session-start"|"session-end"`, `outcome=ok`, `step_type` omitted (optional in the
schema), `tool.arguments={"reason": <matcher value>}` (short enum → safe under every mode,
adapter applies the privacy mode anyway). `harness="claude-code"`, `trace_id=session_id`.

**Security & privacy.** Reason values are enums (no PII). Nothing new is captured from the
environment. The adapter's secret scan still runs on the event.

**Edge cases.** Missing `session_id` → `"unknown"` (existing convention). A `SessionEnd`
without a prior `SessionStart` (e.g., recorder installed mid-session) → still recorded; no
synthetic start. `clear`/`compact`: decide whether they emit an end + new start (recommended:
record the boundary with the reason; do not fork session ids — D-19.1).

**Dependencies.** Adapter phases; daemon loop; replay (M5) consumes the boundaries; F10.

**Testing.** Conformance fixtures `session_start.json`, `session_end.json`; daemon round-trip
asserting first/last records; replay bracket test; a fixture where `SessionEnd.reason=other`
marks the session incomplete.

**Risks & mitigations.** `SessionEnd` hooks share a ~1.5 s budget — a Python spawn (~30–80 ms)
fits but is tight under load; rely on async hooks (P1). Decision D-19.2: treat `clear`/`compact`
as a boundary or as a new session.

**Decision.** D-19.1 (id stability across resume/fork), D-19.2 (clear/compact semantics).

### A2. Record denied tool calls (`PermissionDenied` → `denied`) · M5 · #166

**Why (evidence).** R1 says record every tool call; denied calls are the security-relevant
subset. `Outcome.DENIED` and `SecurityEventType.DENIED` exist in `records.py` but nothing emits
them — dead vocabulary — and CUJ-4's success criterion depends on events being produced.
`PermissionDenied` fires for auto-mode denials.

**Behavior.** A blocked call appears in the timeline with `outcome=denied` and a `denied`
security event naming the tool and reason; analytics can count denials per tool/session.

**Data & schema impact.** Phase `denied`; record `outcome=DENIED`, `step_type=observe`,
`SecurityEvent(type=denied, emitter="claude-code", tool=<tool_name>, reason=<…>)`. Emitter
choice recorded in D-19.3.

**Security & privacy.** The denial reason may echo tool arguments — mask via the secrets
pipeline before storing. This is *recording* a policy decision, never making one.

**Edge cases.** Honest limitation: interactive user rejections do **not** fire a hook — document
that the coverage claim is "auto-mode denials." A `denied` for a call whose `Pre` fired must
retire the pending Pre so no false `hook-error` is synthesized.

**Dependencies.** Daemon `_pending_pre` retirement logic; R5 event plumbing; sibling
agentpolicy semantics (emitter namespace).

**Testing.** Fixture `permission_denied.json`; daemon test asserting the Pre is retired and no
hook-error appears; a denial with a secret in the reason is masked.

**Risks & mitigations.** Over-claiming coverage (mitigation: docs + a conformance gap note).
Emitter confusion with agentpolicy (D-19.3: `claude-code` for harness-native denials).

**Decision.** D-19.3 (emitter).

### A3. Record prompts as reason steps (`UserPromptSubmit`) · M5 · #167

**Why (evidence).** Timelines start at the first tool call; "what was it asked to do" is
missing. `step_type=reason` is defined but unused (PRD 15). PRD 04's "behavior path is unclear"
is half-solved without the prompt step.

**Behavior.** Each prompt is a `reason` step at the head of its turn. Under `metadata-only`
(default) the record shows that a prompt happened and nothing more; under `truncated`/`full`
the redacted prompt is stored (secrets masked even in `full`).

**Data & schema impact.** Phase `prompt`; `tool.name="user-prompt"`, `step_type=reason`,
`tool.arguments={"prompt": <mode-transformed>}`. Reuses `_redact` + `_arguments`.

**Security & privacy.** Prompts are the highest-PII surface; the double gate
(mode + `capture_prompts`) applies. Never use `UserPromptSubmit`'s blocking decision control;
always exit 0.

**Edge cases.** Empty prompt; very large prompt under `truncated` (cap applies); prompt carrying
a secret (fires `secret-detected` and masks). `UserPromptSubmit`'s timeout is lowered to 30 s —
irrelevant for a fire-and-forget command hook, but noted.

**Dependencies.** Privacy modes (M4, shipped); secrets (M4, shipped).

**Testing.** Adapter tests per mode; a secret-bearing prompt asserts masking + event; a fixture
replay for the default (metadata-only) shape.

**Risks & mitigations.** Volume (one record/turn) — negligible vs NFR-3; verify the NFR-3 math
in the soak (K4).

**Decision.** None new; `capture_prompts` already exists.

### A4. Subagent attribution (`agent_id` / `agent_type`, `SubagentStart/Stop`) · M5 · #168

**Why (evidence).** Nearly every Claude Code record has `agent.identity="unknown"` because tool
events carry no agent field — except inside subagents, where the harness supplies
`agent_id`/`agent_type` and we ignore them. M6 analytics and CUJ-6 have nothing to group on.

**Behavior.** Records made inside a subagent are attributed (identity + type); optionally
subagent start/stop appear as boundary records.

**Data & schema impact.** `identity_from()` reads `agent` → else `agent_id`/`agent_type` →
`AgentIdentity(identity=agent_id, name=agent_type)`. Optional phases `subagent-start`/
`subagent-stop` with boundary records.

**Security & privacy.** `agent_type` is a name, not content; safe.

**Edge cases.** Event carries `agent` *and* `agent_id` (prefer explicit `agent`). Subagent
without an id. Trace identity: subagents share the session `trace_id`; spans distinguish
(D-19.4).

**Dependencies.** A1 conventions; M6 rollups.

**Testing.** Adapter test with a subagent-carried event; optional boundary fixtures.

**Risks & mitigations.** Grouping mistakes if subagents should be distinct traces — D-19.4
resolves.

**Decision.** D-19.4 (trace identity across subagents).

