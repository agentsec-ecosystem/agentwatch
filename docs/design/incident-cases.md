# Design — Incident Cases

**BLUF:** A **case** groups the sessions/hosts/days of one real incident into a merged, gap-annotated timeline plus a
self-contained bundle that re-verifies offline. Membership is recorded as **chain records** (the same pattern
[legal-hold](legal-hold.md) uses), so it cannot be edited after the fact without breaking the hash chain, and the bundle
is **manual/local only** — there is no registry egress path.

**Status:** implemented (2026-10-07, v0.2.0 M30) · **Milestone:** M30 · Sources:
[PRD 57 §IR-1](../prd/57-investigation-depth-and-verification.md), [legal-hold.md](legal-hold.md),
[evidence-verifier.md](../reference/evidence-verifier.md), 28.COR-3, 26.TRACE-2.

## Case object

Implemented in `agentwatch.incident_cases`.

- `agentwatch case create --title … [--severity …] [--ref …]` appends one metadata-only chain record; the case ID is a
  stable per-store counter (`C1`, `C2`, …).
- `case add <id> --session <sid>` / `case remove <id> --session <sid>` append `add`/`remove` chain records. An unknown
  case fails closed (`ValueError` → nonzero exit). `case list` reconstructs current membership from the chain.
- Records use the store marker producer and `metadata-only` privacy; no arguments, content, or principals are stored.

## Merged timeline

`case_timeline` merges every member session's records into one ordered timeline and states its rule:

> **ordering:** ascending `started_at` (UTC); tie-break `session_id`, then chain `seq`.

Gaps are **classified**, never silently dropped:

| Class | Meaning |
|---|---|
| `recording-gap` | an explicit `recording-gap` record inside a member session |
| `time-gap` | consecutive merged entries more than one hour apart (delta reported) |
| `purge` | a `session-purge` record inside a member session |
| `tombstone` | a store-level tombstone (payload dropped; attribution unavailable) |
| `unreadable` | a chain line that failed to parse |

## Case bundle

`case export` writes a local zip:

- `case.json` — the case, the ordering rule, the timeline, the classified gaps, and a per-session verdict table
  (`intact`, `records`);
- `records.ndjson` — member-session records with their chain envelope (`seq`/`prev_hash`/`hash`);
- `incident-report.json` — a COR-3-shaped, metadata-only report (`submission.auto_egress: false`, `endpoint: null`);
- `manifest.json` — format/version and the sha256 of every member.

`agentwatch case verify <bundle>` re-checks the member hashes **and** re-hashes each `records.ndjson` row from its
`prev_hash`, so a tampered payload is caught even if an attacker re-computes the manifest hashes. A missing member, a
bad zip, or a malformed segment never raises — it returns a verdict with the problems enumerated.

## Egress

`case export` writes a path and nothing else. There is no endpoint, no upload, and no registry submission: the report is
manual and voluntary, matching COR-3. `egress_audit` keeps the module free of egress-capable imports.

## Testing

- `tests/test_incident_cases.py` — membership changes are chain records; the chain still verifies; the merged timeline
  states its ordering rule and classifies time/explicit/purge/tombstone gaps; the bundle verifies offline and names the
  first tampered member; a re-hashed-manifest chain tamper is still caught; `case export` is local-only.
