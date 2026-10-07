# Design — Legal Hold

**BLUF:** How a **hold** suspends retention and purge for a scope, with recorded provenance and an explicit override,
so litigation preservation does not collide silently with retention windows or right-to-erasure. Holds are chain records;
derived indexes and exports honor them.

**Status:** HLD-1 implemented (2026-10-06, v0.2.0 M29); derived-index propagation BLOCKED on 30.EXT-5 ·
**Milestone:** M29 · Sources: [PRD 56](../prd/56-governance-retention-and-redaction-quality.md),
[storage-design.md](storage-design.md), [derived-postgres.md](derived-postgres.md), PRD 44 (CMP-3).

## Semantics

Implemented in `agentwatch.holds`.

- `hold add --scope <session|project|time-range|principal> --reason … [--ref CASE-123]` → an appended, attributable
  record; `hold list`; `hold release`. The hold ID is derived from its chain position (`H<seq>`).
- While a hold is active, `retention apply` **skips** held records (lists them + hold IDs in `--dry-run`, counted as
  `held`) and `purge` **fails closed** with the hold reference; the refusal is itself a chain record.
- An override path exists but requires a stated reason (`purge --override-reason TEXT`); overrides are recorded as a
  session-scoped `purge-override` chain record, so they are conspicuous in `evidence` and in the compliance report's
  retention row (`holds` / `overrides` counts).

## Interaction with D-K (tombstone, never hard delete)

A hold prevents the tombstone from being written in the first place. If erasure and hold collide, the tool records the
decision rather than choosing silently.

## Propagation

Holds apply to the chain store **now**; the embedded index (LUI-2), the Postgres tier, and other derived/export
artifacts are 30.EXT-5 (M30). A rebuild after release reproduces the index consistently once EXT-5 lands. The
`evidence` bundle already carries the session-scoped override record and the compliance report lists holds + overrides.
ADR-0041. **BLOCKED (declared):** the acceptance criterion "derived indexes and exports honor holds" requires EXT-5 /
LUI-2, which are not in this branch.

## Testing

- Held records survive `retention apply` and a rebuild-from-chain (FT-HLD-1) — `tests/test_legal_hold.py`.
- `purge` on a held session fails closed; override requires a reason and is surfaced.
- Compliance-report retention row lists holds + overrides.
