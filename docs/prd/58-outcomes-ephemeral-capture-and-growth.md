# PRD 58 — Outcomes, Ephemeral Capture & Growth

**BLUF:** Turn the record into outcome facts and cover the runs that matter most: deterministic outcomes (test/build
exits, reverts, interruptions, retained changes) and cost-per-retained-change; a **sealed runner segment** mode for
CI/cloud/background agents that import with chain-of-custody labels; a try-before-install demo bundle; and alert-routing
recipes (routing stays in the user's stack).

**Status:** proposed v0.2.0-expanded (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M28–M29,
v0.2.x candidates · **Depends on:** PRD 53 (PRV), PRD 33 (S6/S7), PRD 42 (TRACE), PRD 36 (S10), PRD 46 (EXA-1) ·
**Extends:** `cost`, `digest`, `demo`, sinks, behavior fingerprint · **Adds:** CUJ-29, CUJ-30

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust
> boundary stays deterministic; monitor-only, R2; local-first/no-egress (R6); no new runtime dependency without a decision
> (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **facts with denominators, never quality scores; artifacts the user uploads, never egress agentwatch
performs.**

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| OUT-1 | Outcome facts + `cost --per retained-change` | Leaders ask cost per shipped change, not per session | 29 |
| OUT-2 | Recurring failure signatures | Competitors cluster failures into prioritized issues | 29 |
| RUN-1 | Sealed runner segments + `import-segment` | Unattended CI/cloud agents are where oversight is thinnest | 30 |
| DEMO-1 | Static synthetic demo bundle | Evaluators want value before wiring hooks | — |
| NTF-1 | Alert-routing recipes | Users want Slack/PagerDuty pings without built-in rules | — |

## OUT-1 — Outcome facts · (new)

**Why.** Platforms sell online evals and trajectory scoring; git-ai sells accepted-rate / "AI-code half-life";
engineering leaders want cost per *retained* change. LLM-judged quality is out of bounds (PRD 29), but deterministic
outcomes exist.
**Behavior.** For each session: test/build/lint command outcomes (cls1 extension), whether the session's commits were
later reverted/reset, interruptions/rejections, retries to success, and — with PRD 53 — whether changes reached a
commit/PR. Reported as facts and ratios; `cost` can show cost per retained change.
**Acceptance.**
- [ ] `outcomes --since 30d --by project|model|harness` shows numerator/denominator and derivation version.
- [ ] `cost --per retained-change` source-stamped.
- [ ] Runs with network disabled and no model configured (determinism test); unknown stays unknown.
**Dependencies.** cls2 (EXT-4), PRV-1. **Decision.** D-58.x — outcome definitions.

## OUT-2 — Recurring failure signatures · (new)

**Why.** LangSmith Insights/Engine cluster failures; agentwatch has `bd1` fingerprints and detectors but no "top
recurring problems this week".
**Behavior.** Deterministic grouping of anomalies/failed calls by signature (tool, error class, cls1 class, fingerprint)
into ranked, evidence-linked patterns in `digest` and the console.
**Acceptance.** Top-N patterns with counts, first/last seen, example sessions, trend vs prior window; grouping rules
versioned; each pattern links to `replay`/`diff`.
**Dependencies.** bd1, detectors, LUI.

## RUN-1 — Sealed runner segments · (new)

**Why.** Background/cloud agents are mainstream; agentwatch has a declared Cursor cloud gap and no stance for runners
with no daemon/home. Those are the unattended runs auditors worry about.
**Behavior.** A lightweight capture mode for ephemeral environments writing a self-verifying sealed segment (own chain,
runner identity, start/end attestation) exported as a CI artifact, then imported with a `source: runner` label and an
explicit custody statement.
**Acceptance.**
- [ ] A CI job records a run and uploads a segment; `agentwatch import-segment` verifies + anchors it; `verify-store` and
      `evidence` handle it; tampered segment fails (FT-RUN-1).
- [ ] Imported records visibly distinguished from locally-chained ones — never presented as locally witnessed.
- [ ] Zero egress by default; redacted records only; attack pack passes on segments.
- [ ] TRACE-1 joins a runner session to the originating local session when `traceparent` present.
**Dependencies.** TRACE-1, S11. **Decision.** ADR-0039.

## DEMO-1 — Demo bundle · (new)

**Why.** Evaluators want to see value before wiring hooks.
**Behavior.** A static, synthetic-data bundle opening in the VFY-1 page, showing replay/impact/oversight/provenance; no
server, no telemetry, no accounts.
**Acceptance.** Opens offline, zero network requests (test); synthetic + secret-scanned; linked from README/GTM.
**Dependencies.** VFY-1, `demo`.

## NTF-1 — Alert-routing recipes · (new)

**Why.** Users ask "how do I get a Slack ping on `secret-detected`?" while agentwatch deliberately forwards events
rule-free and leaves alerting to agentpolicy.
**Behavior.** Executable recipes: OCSF/webhook sink → Alertmanager/Grafana/Slack/PagerDuty for security events, oversight
thresholds (APV-3) and capability changes (CAP-2).
**Acceptance.** Three CI-tested recipes; claims-ledger entries; docs state "routing lives in your stack".
**Dependencies.** EXA-1, SIEM-1, S10.

## Not goals
LLM-judged quality in the trust path; a hosted collector; built-in alert rules; auto-submission to registries.

## Sources
Anthropic measuring-autonomy/auto-mode posts; git-ai stats; LangSmith Engine/Insights; OWASP ASI09; PRD 43 registry notes.
Local analysis files 04, 07, 10.
