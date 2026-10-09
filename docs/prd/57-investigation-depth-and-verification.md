# PRD 57 — Investigation Depth & Evidence Verification

**BLUF:** Deepen the investigation loop to match how incidents and regressions actually look in 2026: an **environment
fingerprint** and delta ("what changed between these sessions?"), **case** packaging across sessions/hosts, a
**concurrency** view for parallel agents, a **browser-based evidence verifier** that needs nothing installed, and
**sandbox-boundary events** ("what did the agent try, and what was blocked?").

**Status:** shipped in v0.2.0 (2026-10-08) — originally proposed v0.2.0-expanded (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M27–M28 ·
**Depends on:** PRD 26 (diff), PRD 33, PRD 31 (evidence/verifier), PRD 51 (CCO), PRD 52 (CAP), PRD 49 (APV) ·
**Extends:** `diff`, `drift`, `at`, `annotate`, `tree`, standalone verifier · **Adds:** CUJ-33, CUJ-34, CUJ-8 extension

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust
> boundary stays deterministic; monitor-only, R2; local-first/no-egress (R6); no new runtime dependency without a decision
> (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **regressions are usually environmental, incidents are usually multi-session, and verification must need
nothing installed.**

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| ENV-1 | Environment fingerprint + delta in `diff`/`drift` | Regressions are model/harness/mode/capability changes, not just tool sequences | 33 |
| IR-1 | Case object + merged timeline + case bundle | CUJ-8 is single-session; incidents span sessions/hosts/days | 34 |
| CNC-1 | Concurrency report + `ambiguous` attribution | Parallel/worktree agents produce overlap and mis-attribution | — |
| VFY-1 | Browser verifier (offline, zero-network) | Auditor shouldn't need a Python runtime to verify | 8 (ext.) |
| SBX-1 | Sandbox-boundary events | The sandbox is the main control; blocked attempts are high-signal | 21 (ext.) |

## ENV-1 — Environment fingerprint & delta · (new)

**Why.** After a regression the first question is "what changed?" Causes are mostly environmental and invisible: model
version (silent swaps), harness version, permission mode, loaded capabilities (PRD 52), rules files, MCP surface, config.
**Behavior.** Each session carries a content-free environment fingerprint; `diff`/`drift` show an environment delta
beside the behavior delta and flag coincident changes; `sessions --group-by-env` groups by fingerprint.
**Acceptance.**
- [ ] `diff a b` prints "model X→Y, harness A→B, +1 skill, CLAUDE.md changed, mode default→auto" above the behavior diff.
- [ ] `drift` annotates shifts with environment changes in the same window ("coincides with", no causal claim) (FT-ENV-1).
- [ ] Fingerprint contains names/versions/digests only; absent facts `unknown`.
**Dependencies.** CAP-1, APV-2, CCO-1. **Decision.** ADR-0042.

## IR-1 — Incident cases · (new)

**Why.** Real incidents span sessions/hosts/people; registries (AIID/AIR) explicitly lack structured evidence.
**Behavior.** `agentwatch case create/add/show/export`; merged, gap-annotated timeline; per-session verdict table +
incident-report file (COR-3 shape).
**Acceptance.** Case membership changes are chain records; merged timeline states ordering rules and classifies gaps;
case bundle verifies offline; no registry egress (test) (FT-IR-1).
**Dependencies.** COR-3, TRACE-2, fleet.

## CNC-1 — Concurrency view · (new)

**Why.** Parallel/worktree/background agents edit the same paths; `blame`/`at` show no overlap. *(Validate demand in
field test before building beyond the report.)*
**Behavior.** Deterministic report of sessions overlapping in time on the same repo/path and shared-file edits;
`provenance` marks multi-session ranges `ambiguous`.
**Acceptance.** `agentwatch concurrency --project . --since 7d`; two-session overlap fixture.

## VFY-1 — Browser verifier · (new)

**Why.** CUJ-8's "verify with nothing installed" still needs a Python runtime (zipapp); an auditor/lawyer/regulator
should only need a browser.
**Behavior.** A static, self-contained page (works from `file://`, no network) that loads a bundle/AAT/Agent Trace export
and re-verifies chain/completeness/leak-scan, showing the same verdicts (plus "recording attested" from PRD 50) as the CLI.
**Acceptance.**
- [ ] Opens from `file://`, zero network requests (test), bundle never leaves the browser (FT-VFY-1).
- [ ] Verdicts equal the CLI verifier on the whole evidence fixture set (differential test).
- [ ] Tampered bundle → clear failure naming the first broken link.
- [ ] The page is a signed, checksummed release artifact listed in release evidence.
**Dependencies.** S12 verifier, PRD 50. **Decision.** ADR-0044.

## SBX-1 — Sandbox-boundary events · (new)

**Why.** The sandbox is now the main safety control (network denied by default; 84% fewer prompts); commands can be
excluded by config; a sandbox-escape CVE exists. The record shows *allowed* calls; blocked attempts and unsandboxed
executions are the highest-signal "what did it try" facts. *(Verify signal availability per harness before committing.)*
**Behavior.** Where exposed: sandbox enabled/disabled per session, commands run outside it, and denied network/file
attempts — metadata-only, attributable to the call.
**Acceptance.**
- [ ] `oversight` includes "% calls unsandboxed" + denial counts by class; `impact` separates attempted-but-blocked
      destinations from contacted ones.
- [ ] Harness exposing none → matrix says so, no inference from absence.
- [ ] Event in the security-event schema with OCSF mapping.
**Dependencies.** CCO-1, DEP-2.

## Not goals
Root-cause inference/auto-bisection; building sandboxes; a hosted verifier; case-management workflow.

## Sources
Claude Code settings-reference (sandbox.excludedCommands; sandbox applies to Bash only); Anthropic containment post;
Agent Trace (PRV-2); AAAI/AIR incident registry notes (PRD 43). Local analysis files 03, 05, 06, 07.
