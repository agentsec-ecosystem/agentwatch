# Design — Code Provenance

**BLUF:** How the record links to the code it produced: `provenance <commit|range|PR|file>` returns the contributing
sessions with per-file/line attribution and a confidence (`exact | heuristic | unknown`); **Agent Trace** (pinned RFC)
export/ingest interoperates with git-ai and other code-provenance tools; range+hash capture keeps attribution accurate
without storing code.

**Status:** proposed (2026-10-05, v0.2.0-expanded) · **Milestone:** M27–M28 · Sources:
[PRD 53](../prd/53-code-provenance-and-attribution.md), [threat-model.md](threat-model.md),
[aat-mapping.md](aat-mapping.md) (pinning pattern).

## Join model

Facts: session records (repo root, VCS revision at start, per-file-modification line ranges + content hashes) + git facts
(commit ↔ tree ↔ file ranges). `provenance` joins on (repo, revision/time-window, path, range hash).

| Confidence | When |
|---|---|
| `exact` | a structured edit argument gave the range, or the range hash matches |
| `heuristic` | tool did not expose a range; file-level attribution only |
| `unknown` | no recorded session covers the range |

A commit with no recorded session → "no recorded agent activity" (never "human"). Human edits after the agent →
`mixed`. Coverage gaps in the window are flagged; no completeness claim beyond the chain.

Implementation (`agentwatch.provenance.build_provenance`, CLI `agentwatch provenance`): a `GitFacts` source reads a
commit's changed paths and hunks read-only (`git show --unified=0`, never writing to the repo) and degrades to an
honest `unavailable`/unknown instead of guessing; PR targets resolve offline by matching a merge/squash subject
`(#N)`. Records are joined by normalized path + a session window (default 7 d) and a direct session-start `vcs.commit`
link. Per hunk the confidence is `exact` (a structured range covers it), `mixed` (part of the hunk has no recorded
agent activity), `ambiguous` (two or more sessions edited the same range — CNC-1), `heuristic` (file-level only), or
`unknown` (no recorded session). Each contributing session carries harness/model, the authorization mix, cost,
anomalies, coverage, and an evidence pointer. Loaded capabilities are not recorded in this build (M30 CAP-1) and are
reported as a note, never invented. Read-only on the repo by default.

## Range+hash capture (PRV-3)

Per file-modifying call, under **every** privacy mode: affected line ranges + content hashes (keyed), **no content**.
This is the minimum for line attribution; without it, attribution falls back to file-level `heuristic`. ADR-0033.

Implementation: `agentwatch.provenance.capture_ranges` reads the structured edit arguments (a range from
`start_line`/`end_line`, `line_range`, or `lines`; the replaced/new content from `new_string`/`content`/…), emits a
`RangeCapture` (ranges + keyed HMAC-SHA256 hashes), and never emits content or a diff. The fact is **metadata**, so it
is legal under `metadata-only`; it rides in the reserved `tool.arguments` key `agentwatch_attribution`
(`RANGE_CAPTURE_VERSION = "prv3"`). `range_facts_from_record` reads it back; `is_content_free` is the defensive guard.
When the harness exposes no range the capture is file-level `heuristic` (documented fallback). Declared gap: persisting
the reserved fact from the live hook before redaction is owned by the record/redaction path (another workstream); the
primitive and its content-free property are proven here.

## Agent Trace export/ingest (PRV-2)

- `export-session <id> --format agent-trace` emits spec-conformant records (ranges, conversation ref, contributor
  type/model, VCS revision); `unmapped` explicit; pinned revision + drift job.
- A read-only reader accepts existing Agent Trace / git-ai notes for **cross-validation** (agree / disagree /
  agentwatch-only / notes-only) — never duplicate.
- Writing into a repo is a separate, explicit, consented command; default is export-to-file. Claim language cites the
  spec revision, never "conformant".

## Privacy

Export contains ranges/hashes/ids only; passes the redaction attack pack. Read-only on the repo by default.

## Testing

- commit→session resolves <2 s; "no recorded activity" correct (FT-PRV-1).
- mixed range correct; export validates against pinned schema; zero code content.
- Differential: `agree/disagree` vs existing git-ai notes.

## Decision

ADR-0033 (range+hash capture, content-free), ADR-0034 (Agent Trace pin + write policy).
