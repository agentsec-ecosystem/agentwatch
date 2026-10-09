# ADR-0041 — Legal hold suspends retention/purge, with recorded provenance

- **Status:** accepted (2026-10-06, v0.2.0 M29 HLD-1)
- **Context:** Retention windows (AAT §9 12mo) and the right to erasure (`purge`)
  collide with litigation holds. A hold that is only "don't run retention" by
  convention is invisible to an auditor, and a mistaken purge is irreversible.
- **Decision:**
  1. A hold is a metadata-only append to the hash chain naming a **scope**
     (`session` / `project` / `time` / `principal`), a reason, and an optional
     external ref. `agentwatch hold add|list|release` manages them; the hold ID is
     derived from its chain position (`H<seq>`).
  2. While a hold is active, `retention apply` **skips** held records (listed with
     their hold IDs under `--dry-run`) and `purge` **fails closed**: nothing is
     tombstoned, the refusal is itself a chain record, and `blocked_by_hold` names
     the hold.
  3. An override is possible only with a stated reason. It is recorded as a
     `purge-override` chain record attached to the session, so it is conspicuous
     in an **evidence bundle** and in the compliance report's retention row.
  4. Holds/releases/refusals/overrides are all hash-chain records. D-K is
     preserved: a hold prevents the tombstone from being written at all, and
     agentwatch never hard-deletes.
- **Consequences:** Held records survive retention and a rebuild-from-chain. This
  decision lands the hold semantics and its integration with the existing
  retention/purge paths; propagation to *every* derived index/export is 30.EXT-5
  (M30, behind the embedded index LUI-2) and is a declared open item, not silently
  assumed here.
- **Alternatives rejected:** a separate hold file beside the store (not
  tamper-evident, not portable in an evidence bundle); hard-deleting on override
  (breaks D-K); auto-overriding on a time expiry (a legal hold ends only when a
  human releases it).