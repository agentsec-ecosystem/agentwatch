# PRD 54 — Local Console & Embedded Query Tier

**BLUF:** Give the hook-recorded store a first-minute visual and a query tier that ships with the CLI. One command
(`agentwatch ui`) opens a loopback-only, read-only console over the local chain store — no Docker, no services, no
account; a zero-ops, rebuildable embedded index makes long-window search interactive while the chain store stays the sole
source of truth. This re-sequences the Postgres tier (PRD 41 PG-1..3) behind the console.

**Status:** shipped in v0.2.0 (2026-10-08) — originally proposed v0.2.0-expanded (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M26–M28 ·
**Depends on:** PRD 42 (STR-1/2), ADR-0019 (derived index), PRD 28 · **Extends:** `view` TUI, operator UI, PG-1..3, STR-2 · **Adds:** CUJ-24

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust
> boundary stays deterministic; monitor-only, R2; local-first/no-egress by default (R6); no new runtime dependency without
> a decision (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **the console is the reference viewer of the record, not a dashboard product** (PRD 14 reframed). It reads
the same chain the CLI does and never becomes a second source of truth.

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| LUI-1 | `agentwatch ui`: local browser console over the chain store | The only browser UI needs 6 Docker services and misses hook records; first impressions are visual | 24 |
| LUI-2 | Embedded, rebuildable query index | JSONL doesn't scale for interactive long-window search; PG is heavy and slip-prone | 24 |

## LUI-1 — `agentwatch ui` · (new)

**Why.** README promises ≤15 min, local-first; the docs' operator UI is a 6-service Compose stack fed by SDK/OTLP, not
the hook store a Claude Code/Cursor user has. Competitors give a browser view in one command, and that view is how
evaluators form an opinion. PG (the planned unification) is PRD 40's "largest item, first to slip".

**Behavior.** One command opens a loopback token-gated, read-only web console: sessions → timeline/replay → record
detail, with `impact`, `coverage`, `cost`, `oversight` (PRD 49), capability diff (PRD 52), `provenance` (PRD 53) and an
"Export evidence" action; live updates via STR-1/2. Same console can point at a fleet/Postgres tier when present.

**Acceptance.**
- [ ] From a machine with one recorded session: **browser view in < 60 s**, no Docker, no extra services (FT-LUI-1).
- [ ] Loopback only; per-launch token; read-only (no mutation endpoint exists); no egress (egress audit test).
- [ ] UI numbers equal CLI `--json` (parity test for sessions/impact/cost/coverage).
- [ ] Broken chain / tombstones / gaps rendered visibly; redaction state ("receipts") per record; privacy mode in header.
- [ ] axe accessibility gate passes; keyboard navigation; works with any harness + `source: sdk` side by side.

**Data & schema impact.** None (reads the store/index).
**Security & privacy.** Local loopback + token; no egress; read-only.
**Dependencies.** LUI-2, STR-1, P7/GOV role model (PRD 56) for any multi-user tier.
**Risks & mitigations.** Scope creep into a dashboard product → PRD 14 reframe. CSRF/DNS-rebind → ADR-0036. **Decision.** ADR-0036.

## LUI-2 — Embedded query tier · (new)

**Why.** Interactive search over months of JSONL is slow; PG is the only planned tier and is heavy/slip-prone; every
competitor leads with fast trace querying. ADR-0019's derived/rebuildable invariant fits a zero-ops embedded index.

**Behavior.** A zero-ops, rebuildable index created/refreshed from the chain store, used by CLI + console; deletable at
any time with no data loss; `verify-store` unaffected; optional columnar export (`export --format parquet`) for
notebook/BI users. Postgres becomes the fleet/multi-tenant tier (PRD 41 PG-2), not the only tier.

**Acceptance.**
- [ ] Delete the index → every command still works (slower) and rebuilds identically (bit-for-bit rebuild test).
- [ ] `search`/`sessions`/`cost`/`oversight` on a 1M-record store meet the published target in `performance.md`.
- [ ] No heavyweight runtime dependency (NFR-5 decision in ADR-0035).
- [ ] `purge`/retention propagate to the index (EXT-5) and rebuild stays consistent.

**Dependencies.** ADR-0019, STR-1, PRD 50/56 (holds).
**Risks & mitigations.** Index drifting from chain → architectural invariant + rebuild test. **Decision.** ADR-0035.

## Not goals
Multi-tenancy/remote access (PG-2); a hosted console; editing data; replacing the CLI/TUI.

## Sources
PRD 41/40; `design/derived-postgres.md`; LangSmith SmithDB / Langfuse-ClickHouse notes; Phoenix local-server note. Local analysis files 03, 06, 07.
