# ADR-0035 — Embedded query index tier (and re-sequencing Postgres behind it)

- **Status:** accepted (2026-10-07, v0.2.0 M30 LUI-2 / EXT-8)
- **Context:** PRD 54 §LUI-2 and [design/local-console.md](../design/local-console.md) need a query tier that
  ships with the CLI and console, works on a clean install with **no services**, and does not repeat the
  Postgres tier's operational weight and slip risk (PRD 40: PG is "the largest item, first to slip"). ADR-0019
  already fixes the invariant that any analytics tier is **derived and rebuildable** from the hash-chained
  JSONL store. NFR-5 requires a recorded decision before any new runtime dependency.
- **Decision:**
  1. **The general-case query tier is an embedded, rebuildable index over the chain store.** It is built from
     the store, used by the CLI (`agentwatch index`, and by `search`/`sessions` when fresh) and the console,
     and is deletable at any time: deleting it loses nothing, every command still works (slower) by reading the
     chain, and it rebuilds **bit-for-bit** from the chain. The chain stays the sole source of truth (ADR-0019).
  2. **No heavyweight runtime dependency.** The index is a stdlib `sqlite3` artifact — the only new dependency
     surface is the Python standard library, so it needs no install and no service. This is the NFR-5 decision.
  3. **Columnar export is optional.** `export-parquet` (`QueryIndex.export_parquet`) lazily imports `pyarrow` and
     raises `ParquetUnavailableError` when absent; `pyarrow` is an optional extra (`agentwatch[parquet]`), never a
     core dependency and never imported at module load.
  4. **Postgres is re-sequenced behind the embedded tier.** It becomes the **fleet / multi-tenant** tier
     (PRD 41 PG-2), not the only tier: the embedded index is the default for a single-operator local install,
     and Postgres is only warranted for cross-host fleet analytics and tenant isolation. The derived-only
     invariant is unchanged and applies to both tiers. See
     [design/derived-postgres.md](../design/derived-postgres.md).
  5. **Freshness is tombstone-aware.** A purge or retention pass rewrites an entry as a tombstone while keeping
     its chain hash; the index freshness digest therefore includes the tombstone bit, so a purge invalidates the
     index and the next use rebuilds it from the now-tombstoned chain (EXT-5).
- **Consequences:** Zero-ops interactive search on a clean install (measured: 1M-row indexed session lookup
  ≈2 ms); a bit-for-bit rebuild test becomes a release gate; the store/index/exports must all be covered by
  purge propagation (EXT-5); `verify-store` never consults the index. Postgres work is de-risked rather than
  dropped.
- **Alternatives rejected:** Postgres-first (heavy, slip-prone, needs Docker/services for a first-minute view);
  a bespoke binary index format (unnecessary when stdlib `sqlite3` is deterministic and portable); an eager
  `pyarrow`/`pandas` dependency (violates NFR-5 for a feature most users never touch).
