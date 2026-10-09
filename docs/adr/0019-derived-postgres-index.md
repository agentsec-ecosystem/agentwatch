# ADR-0019 — Derived Postgres index

- **Status:** proposed (2026-10-05, v0.2.0; phaseable to v0.2.1)
- **Context:** see [PRD 41](../prd/41-standards-and-interop-ii.md) PG-1..3, PRD 14 (SDK-unification decision) and
  [design/derived-postgres.md](../design/derived-postgres.md). JSONL does not query at fleet scale.
- **Decision:** Postgres is a **derived, rebuildable** index; the hash-chained store remains the sole source of
  truth; `verify-store` never consults Postgres; multi-tenant isolation lives at the index layer with cross-tenant
  reads denied-and-audited; SDK spans land in the unified store with the source distinction preserved.
- **Consequences:** Fleet-scale queries and team adoption without eroding the integrity story; a rebuild invariant
  (bit-for-bit) and a drop-Postgres CI leg become release gates.
