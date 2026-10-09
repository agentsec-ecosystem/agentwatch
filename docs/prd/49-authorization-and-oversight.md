# PRD 49 — Authorization & Oversight Provenance

**BLUF:** Make the record answer *who or what authorized each action* and *whether oversight was real* in the
2026 permission world, where the default is a **model classifier** (auto mode), bypass mode is common, and humans
approve 93–97% of prompts. Extend the S14 approval field into a versioned authorization taxonomy (human / rule /
classifier / hook / bypass / not-required / denied / unknown), record **permission mode as a time-varying fact**,
and publish an **`oversight` report** that turns human-in-the-loop into data. This closes the flagship journey's
gap: today the record can answer "what happened" but mis-answers "did a human approve that?".

**Status:** shipped in v0.2.0 (2026-10-08) — originally proposed v0.2.0-expanded (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M26–M28 ·
**Depends on:** PRD 19, PRD 35 (S14), PRD 44 (IDN-1) · **Extends:** S14 approval provenance, CUJ-14 · **Adds:** CUJ-21

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust
> boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only, every hook exits
> 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency without a recorded decision
> (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **a guessed consent is a false audit record.** The value space must describe the *actual* decider, and
`unknown` must stay the honest default wherever the harness does not expose the fact.

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| APV-1 | Authorization source taxonomy v2 (classifier, bypass, hook, rule, human once/remembered) | Auto mode is the default; humans rubber-stamp; "did a human approve it?" is the first incident question | 21 |
| APV-2 | Permission mode per call + transition records | Mode changes mid-session (fallback, pins); auditors need the mode at the moment of the action | 21 |
| APV-3 | `oversight` report (authorization mix, approve/reject, decision latency, destructive × source) | Regulators/CISOs ask whether oversight is *effective*; only the record layer can compute it | 21 |

## APV-1 — Authorization source taxonomy v2 · v0.2.0-expanded · (extends S14)

**Why.** `design/approval-provenance.md` models `{user, auto, not-required, denied, unknown}`, where `auto` means an
allow-list rule. Claude Code's default is now **auto mode**, where a separate model classifier approves or blocks
each action; users approve ~93–97% of prompts; ~25% of interactive sessions start in bypass; 62% of users have used
bypass or "don't ask again" (`docs/reference/v0.2.0-research-sources.md` §5, Anthropic 2026). The current field
therefore records classifier approvals as `unknown` (or, worse, a developer reads `outcome=ok` as consent).

**Behavior.** A versioned authorization vocabulary stored on the record (metadata-only), separating at minimum:
`human-once`, `human-remembered`, `rule` (allow-list/settings), `classifier` (model-reviewed), `hook`, `bypass`,
`not-required`, `denied` (sub-attributed to human/rule/classifier/hook), and `unknown`. The taxonomy is published
like the classifier table and carries an explicit legacy mapping from the S14 five values.

**Data & schema impact.** Additive authorization object on existing records; `search --approval` accepts old and new
values; AAT export maps it or declares it `unmapped` (lossless-or-explicit).

**Security & privacy.** Metadata only; safe under every privacy mode. No judgement of correctness.

**Acceptance (what good looks like).**
- [ ] For Claude Code, a classifier-approved call is `classifier`, never `user`/`auto`; a bypass-mode call is
      `bypass` even with no prompt.
- [ ] Every value has a fixture proving its derivation; every indeterminate case is `unknown` with a reason, and a
      test proves no value is inferred from `outcome=ok`.
- [ ] Taxonomy + legacy mapping published in `reference/record-format-spec.md`, `design/data-dictionary.md`, and the
      OCSF/CloudEvents mappings.
- [ ] Other harnesses (Cursor/Gemini/Codex) map their permission facts or declare `unknown` per capability.

**Dependencies.** CCO (PRD 51) makes Claude Code's classifier/decision facts authoritative; per-adapter fixtures.

**Risks & mitigations.** Taxonomy churn → versioned, additive; mis-typed `user` → fixtures + field case FT-APV-1.
**Decision.** ADR-0027 — authorization taxonomy v2 + legacy mapping.

## APV-2 — Permission mode as a first-class, time-varying fact · v0.2.0-expanded · (new)

**Why.** Mode changes within a session (Shift+Tab, auto-mode fallback after repeated blocks, admin pins). A single
per-session label would misrepresent the moment of a destructive action.

**Behavior.** The active permission mode is recorded on every call; every mode *transition* is recorded as its own
observation. `replay`, `view`, `impact`, `blame`, `evidence`, `sessions` and the compliance report surface mode.

**Acceptance.**
- [ ] `search --mode bypass --since 30d` works; `replay <id>` marks transitions.
- [ ] A default→bypass→default fixture reconstructs correctly and flags the bypass interval in `impact`.
- [ ] Missing mode data → `unknown`, counted in `coverage`.

**Dependencies.** APV-1; CCO for native mode-change events.
**Risks & mitigations.** Harness does not expose mode → declared gap, never inferred.
**Decision.** Covered by ADR-0027.

## APV-3 — `oversight` report · v0.2.0-expanded · (new)

**Why.** Anthropic's own data shows manual review is largely reflexive (testers caught a swapped dangerous command
13.6% of the time); EU AI Act Art. 14 and OWASP ASI09 (*Human-Agent Trust Exploitation*) ask about oversight
effectiveness. Only the record layer can compute it, and nobody open does.

**Behavior.** `agentwatch oversight [--since] [--project] [--by day|user|mode|tool-class] [--json]` reports: share of
calls by authorization source; share of sessions by mode; for human-prompted calls — approve/reject rate and
time-to-decision distribution; and a cross-tab of **cls1 destructive/network/credential-adjacent calls ×
authorization source**. Facts only; no "score"; integrated into `digest` and the compliance report.

**Acceptance.**
- [ ] Deterministic, offline, version-stamped (classifier + taxonomy versions).
- [ ] The cross-tab answers "how many `command:destructive` calls ran under bypass/classifier last 30 days?" in one
      command; matches hand-computed totals on the field corpus (FT-APV-2).
- [ ] Latency shown only when both prompt and decision timestamps exist; otherwise "n/a (n calls)".
- [ ] Appears as Art. 14 / ASI09 rows in the compliance report.

**Security & privacy.** Read-only over redacted records; identity stays hashed (IDN-1).
**Dependencies.** APV-1, APV-2, cls1, IDN-1.
**Risks & mitigations.** Read as a quality score → wording is ratios-with-denominators; no verdict.
**Decision.** D-49.x — oversight metric definitions and surfaces.

## Not goals

Judging whether a decision was correct; enforcing any decision; naming individuals (identity stays hashed).

## Sources

Anthropic "How we built Claude Code auto mode" (2026-03-25); "Auto mode is now the default…" (2026-08-07);
"How we contain Claude" (2026-05-25); Claude Code permission-modes docs; OWASP Top 10 for Agentic Applications 2026
(ASI09); EU AI Act Art. 14. Full ledger: `docs/reference/v0.2.0-research-sources.md` §5 and the local analysis
`07-evidence-and-sources.md`.
