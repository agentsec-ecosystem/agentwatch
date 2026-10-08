# Design — Local Console

**BLUF:** How `agentwatch ui` gives a **zero-Docker, loopback-only, read-only** browser view of the local chain store in
one command, and how the **embedded, rebuildable query index** makes long-window search interactive while the chain
store stays the sole source of truth. Postgres (PRD 41 PG) becomes the optional fleet/multi-tenant tier, not the only tier.

**Status:** proposed (2026-10-05, v0.2.0-expanded) · **Milestone:** M26 (index) – M27 (console) · Sources:
[PRD 54](../prd/54-local-console-and-query-tier.md), [derived-postgres.md](derived-postgres.md),
[streaming-views.md](streaming-views.md), ADR-0019.

## Why a local console

The docs' operator UI is a 6-service Compose stack fed by SDK/OTLP; a Claude Code/Cursor user's hook-recorded sessions
have no browser view. One command → a browser is how evaluators form an opinion, and the ≤15-minute promise implies it.

## Surfaces

sessions → timeline/replay → record detail, plus tabs for `impact`, `coverage`, `cost`, `oversight`, capability diff,
`provenance`, and an "Export evidence" action. Live updates via STR-1/2.

## Security model (ADR-0036)

- Binds **loopback only**; a **per-launch token** in the URL; host-header check (DNS-rebinding defense).
- **Read-only**: no mutation endpoint exists (enumerated by test). No egress (egress-audit test).
- Same redaction state as the CLI ("receipts"); privacy mode shown in the header.
- Broken chain / tombstones / gaps rendered visibly.

## Embedded query index (LUI-2, ADR-0035)

- A zero-ops, **derived, rebuildable** index (ADR-0019 invariant); delete it → every command still works and it rebuilds
  **bit-for-bit**.
- Serves CLI + console; optional `export --format parquet` for notebooks (redaction-gated).
- No heavyweight runtime dependency (NFR-5 decision recorded).
- `purge`/retention/holds propagate to the index (EXT-5).

## Parity

UI numbers equal CLI `--json` (sessions/impact/cost/coverage) — a differential test. Accessibility gate (axe) passes;
keyboard navigation for the timeline.

## Testing

- Clean install → browser view of a recorded session ≤60 s (FT-LUI-1).
- Bit-for-bit rebuild; drop-index CI leg; cross-check UI vs CLI.
- Zero network requests from the console process.

## Decision

ADR-0035 (embedded index + dependency), ADR-0036 (console security model).

## Implementation (M30 LUI-1/LUI-2)

`agentwatch.ui.ConsoleServer` serves the console over a stdlib `http.server` on loopback (no Docker). Routes:
`/` (HTML shell), `/api/health` (chain gaps/tombstones/parse errors + index freshness), `/api/sessions`,
`/api/session/<id>` (timeline/replay), `/api/impact/<id>`, `/api/cost`, `/api/coverage`, `/api/oversight`,
`/api/live*` (STR-2 tail: `/api/live/timeline`, `/api/live/anomalies`, and an SSE `/api/live/stream`), and
`/api/export/<id>` (read-only NDJSON). Every route requires the per-launch token and a loopback `Host`; only
`GET` exists. `agentwatch.index.QueryIndex` backs the query paths and is refreshed from the chain
([ADR-0035](../adr/0035-embedded-query-index.md)). UI JSON equals CLI `--json`.

## Live views (M30 UI-1)

The console's live timeline, live anomaly inbox, and streaming tail consume the M26 STR-2 store-truth tail
([`agentwatch.live.LiveTail`](../../packages/python-sdk/src/agentwatch/live.py)): the store remains
authoritative, a backpressured subscriber is **back-filled from the store** and `degraded` stays visible, and
gaps are classified (`stream-drop`/`purged`/`missing`/`rotated`) and rendered — never silent. The anomaly inbox
is a derived, content-free filter (denied/error/security-event records). No mutation, no egress.


