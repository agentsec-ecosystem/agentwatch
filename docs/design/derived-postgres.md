# Design — Derived Postgres Index

**BLUF:** How the v0.2.0 analytics tier works while the **hash-chained store remains the source of truth**: Postgres
is a derived, rebuildable index that can be dropped at any time; multi-tenant isolation lives in the index layer;
SDK spans unify through the same store. **How** — the requirement is
[PRD 41](../prd/41-standards-and-interop-ii.md) (PG-1..3).

**Status:** proposed (2026-10-05, v0.2.0; phaseable to v0.2.1) · **Milestone:** M27 · Re-sequenced (M30 EXT-8) ·
Sources: [PRD 41](../prd/41-standards-and-interop-ii.md), PRD 14 (SDK unification decision), S11 `union`,
`data-dictionary.md`.

> **Re-sequenced (v0.2.0-expanded):** the general-case query tier is now the **embedded, rebuildable index** in
> [`local-console.md`](local-console.md) ([PRD 54](../prd/54-local-console-and-query-tier.md), ADR-0035), which ships with
> the CLI and console and needs no Postgres. Postgres becomes the **fleet / multi-tenant** tier (PG-2) and, per PRD 40's
> cut-line, is phased behind the embedded index; the derived-only invariant below is unchanged and applies to both tiers.

## Re-sequencing decision (EXT-8)

**Decision (recorded):** the **embedded, rebuildable query index** (M30 LUI-2, ADR-0035) is the general-case
query tier and ships with the CLI and the local console; **Postgres is the fleet / multi-tenant tier** (PG-2),
required only for cross-host fleet analytics and tenant isolation. PG-1..3 are therefore phased behind the
embedded index rather than being the only tier. The embedded index is the reference implementation of the
derived/rebuildable invariant above; Postgres must satisfy the same invariant (drop it, rebuild bit-for-bit) and
`verify-store` still never consults it. This decision supersedes the "Postgres-first" reading of
[PRD 41](../prd/41-standards-and-interop-ii.md) and is recorded in
[ADR-0035](../adr/0035-embedded-query-index.md) (which folds in EXT-8; no separate ADR is created).

## Invariant: derived, never authoritative

1. The JSONL chain store is the **only** source of truth. Postgres holds no fact that cannot be rebuilt from it.
2. `agentwatch db rebuild` reproduces the index **bit-for-bit** from the chain; a rebuild divergence is a test
   failure.
3. **Drop-Postgres mode:** with no Postgres reachable, every read command still works (slower) directly from the
   chain. CI runs a no-Postgres leg.
4. `verify-store` verifies the chain, never Postgres.

## Schema seeding

The analytics schema follows [`data-dictionary.md`](data-dictionary.md) (the Postgres schema doc already scoped for
v0.2.0+). Records are projected into typed tables (sessions, records, events, usage, identity, detectors) with a
`source_seq`/`source_hash` back-reference per row for rebuild and audit.

## Multi-tenancy (PG-2)

- A `tenant` boundary is applied at the index layer; every query is tenant-scoped.
- A cross-tenant read returns **nothing** and is recorded as a `store-access` audit record (S21) — a denied read is
  evidence too.
- The chain store remains per-tenant on disk; tenancy never weakens the integrity story.

## SDK unification (PG-3)

- SDK spans and hook records land in the **same unified store** (chain-protected) rather than only the read-time
  `union` (S11).
- The integrity distinction between sources is preserved and visible (`source: hook | sdk | import | proxy | …`).
- The two-producer ordering/identity design is the deferred PRD-14 decision; it is recorded as an ADR (0019) before
  implementation.

## Testing

- Bit-for-bit rebuild test; no-Postgres CI leg; cross-tenant denial + audit; `source` distinction preserved.
