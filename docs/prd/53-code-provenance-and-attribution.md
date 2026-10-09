# PRD 53 — Code Provenance & Attribution

**BLUF:** Connect the record to the code it produced. `agentwatch provenance <commit|range|PR|file>` answers "which
session wrote these lines, under what authorization, at what cost, with which capabilities loaded", carrying
`exact | heuristic | unknown` confidence; **Agent Trace** export/ingest (pinned RFC) makes agentwatch an evidence-grade
source for the code-attribution ecosystem (Cursor, Cognition, git-ai, Jules, Amp, OpenCode, Cline) rather than a silo.

**Status:** shipped in v0.2.0 (2026-10-08) — originally proposed v0.2.0-expanded (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M27–M28 ·
**Depends on:** PRD 33 (S3/S18), PRD 35 (S16), PRD 49 (APV), PRD 52 (CAP) · **Extends:** `impact`, `blame`, evidence, S16
git snapshot · **Adds:** CUJ-22

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust
> boundary stays deterministic; monitor-only, R2; local-first/no-egress (R6); no new runtime dependency without a decision
> (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **attribution is a claim with a confidence, never an assumption.** A commit with no recorded session says
so; hand edits are `mixed`; gaps are flagged.

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| PRV-1 | `provenance` commit/range/PR/file → sessions, approvals, cost | Reviewers/auditors ask which lines came from AI, under what oversight | 22 |
| PRV-2 | Agent Trace export + git-ai notes cross-validation | Open spec (Cursor et al.), Thoughtworks Radar; interop, not a silo | 22 |
| PRV-3 | Content-free range+hash capture (+ ADR) | Line attribution needs ranges; the guarantee forbids storing content | 22 |

## PRV-1 — `provenance` · (new)

**Why.** 2026 converged on code attribution: Agent Trace (RFC v0.1, Jan 2026) supported by Cursor, Cognition, Cloudflare,
Vercel, Google Jules, Amp, OpenCode, Cline, git-ai; Cursor Blame (enterprise); git-ai notes surviving rebase/squash.
`blame` answers "which sessions touched this file" but not "which lines in this commit, under what approval".

**Behavior.** `agentwatch provenance <commit|range|PR|file[:lines]>` returns contributing sessions, harness/model,
authorization mix (PRD 49), cost, anomalies, coverage status, loaded capabilities, and an evidence-bundle pointer.

**Acceptance.**
- [ ] A commit from a recorded session resolves to that session in < 2 s; a commit with no recorded session says "no
      recorded agent activity", not "human" (FT-PRV-1).
- [ ] Hand-edited-after-agent ranges are `mixed`; confidence `exact|heuristic|unknown` shown per range.
- [ ] Sessions with coverage gaps in the window are flagged — no completeness claim the chain can't back.
- [ ] Works offline on a clone; read-only on the repo by default; included in `evidence` + compliance report.

**Data & schema impact.** Derived view over records + git facts; no record-schema change.
**Security & privacy.** Read-only; redacted records only.
**Dependencies.** PRV-3, APV-1, S3/S18.
**Risks & mitigations.** Over-claim / mis-attribution → confidence labels + honest "no activity". **Decision.** ADR-0033.

## PRV-2 — Agent Trace export/ingest · (new)

**Why.** Agent Trace is storage-agnostic and invites implementers; being the first *evidence-grade* source (chain behind
it) repeats the AAT first-mover play. Interop prevents a silo next to the code-provenance standard.

**Behavior.** `export-session <id> --format agent-trace` emits spec-conformant trace records (file/line ranges,
conversation ref, contributor type/model, VCS revision), `unmapped` explicit. A read-only reader accepts existing
Agent Trace / git-ai notes to **cross-validate** (agree/disagree classified), never duplicate.

**Acceptance.**
- [ ] Validates against the pinned schema revision; pin + drift job (AAT-5 pattern).
- [ ] Contains no code content (ranges/hashes/ids only); passes the redaction attack pack.
- [ ] Repos with git-ai notes show per-commit `agree/disagree/agentwatch-only/notes-only` in `provenance`.
- [ ] Writing into a repo is a separate, explicit, consented command; default is export-to-file only.
- [ ] Claim language cites the exact spec revision; never "conformant to the standard".

**Dependencies.** PRV-1, AAT-5 pinning. **Risks & mitigations.** RFC churn / ownership change → pin + "as of revision X".
**Decision.** ADR-0034.

## PRV-3 — Range+hash capture · (new)

**Why.** Line attribution needs facts the metadata-only default drops. Without a deliberate decision, PRV-1/2 will be
inaccurate or quietly erode the "no content stored" guarantee.

**Behavior.** A privacy-reviewed minimum: per file-modifying call, record affected line ranges and content hashes (not
content), computed under every privacy mode.

**Acceptance.**
- [ ] Under `metadata-only`, ranges+hashes exist and no content/diff text does (property + attack-pack tested).
- [ ] Docs state which edit tools/harnesses support range capture; others fall back to file-level with `heuristic`.
- [ ] Performance within the DEP-3 hook budget.

**Dependencies.** PRD 50 (budget), privacy review. **Decision.** ADR-0033.

## Not goals
Building rebase/squash line-tracking (git-ai's domain); editor decorations; pushing attribution anywhere automatically.

## Sources
agent-trace.dev / github.com/cursor/agent-trace (RFC v0.1, 2026-01); cognition.com/blog/agent-trace; InfoQ (2026-02-04);
Thoughtworks Radar; cursor.com Blame docs; github.com/git-ai-project/git-ai. Local analysis files 03, 07.
