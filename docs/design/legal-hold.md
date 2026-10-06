# Design — Legal Hold

**BLUF:** How a **hold** suspends retention and purge for a scope, with recorded provenance and an explicit override,
so litigation preservation does not collide silently with retention windows or right-to-erasure. Holds are chain records;
derived indexes and exports honor them.

**Status:** proposed (2026-10-05, v0.2.0-expanded) · **Milestone:** M27 · Sources:
[PRD 56](../prd/56-governance-retention-and-redaction-quality.md), [storage-design.md](storage-design.md),
[derived-postgres.md](derived-postgres.md), PRD 44 (CMP-3).

## Semantics

- `hold add --scope <session|project|time-range|principal> --reason … [--ref CASE-123]` → an appended, attributable
  record; `hold list`; `hold release`.
- While a hold is active, `retention apply` **skips** held records (lists them + hold IDs in `--dry-run`) and `purge`
  **fails closed** with the hold reference.
- An override path exists but requires a stated reason; overrides are conspicuous in `evidence` and the compliance report.

## Interaction with D-K (tombstone, never hard delete)

A hold prevents the tombstone from being written in the first place. If erasure and hold collide, the tool records the
decision rather than choosing silently.

## Propagation

Holds apply to the chain store, the embedded index (LUI-2), the Postgres tier, and any derived/export artifact; a rebuild
after release reproduces the index consistently. `evidence` bundles reference the active hold. ADR-0041.

## Testing

- Held records survive `retention apply`, `purge`, and index rebuild (FT-HLD-1).
- `purge` on a held session fails closed; override requires a reason and is surfaced.
- Compliance-report retention row lists holds + overrides.
