# Design — Local Storage

**BLUF:** Local-first, append-only record store with hash-chaining; export is opt-in.

Status: **shipped** (v0.1.0 M4; retention controls + single-session purge M9).

## Implementation

- **Module:** `agentwatch.store.RecordStore` — append-only JSONL at
  `<store.path>/records.jsonl`.
- **Envelope:** `{"seq", "prev_hash", "hash", "record"}`; `hash = sha256(prev_hash + canonical_json(record))`,
  genesis `prev_hash = "0"*64`.
- **Verify:** `RecordStore.verify()` recomputes each live entry and checks every link; a break is reported as
  `ChainStatus(ok=False, broken_at=<seq>)` and surfaced by `agentwatch verify-store` (exit 1) — never silent (F4).
- **Retention:** entries older than `retention_days` are rewritten as tombstones
  (`{"seq","prev_hash","hash","tombstone":true,"purged_at"}`) that keep the chain links; `max_size_mb` reached
  makes `append` raise `StoreFullError` and stop recording without overwriting (F3). `agentwatch retention apply`
  runs a retention pass on demand and exits non-zero if the chain is not green (M9).
- **Purge (right to erasure, M9):** `RecordStore.purge_session` tombstones one session's records and appends a
  metadata-only `session-purge` marker (who/why); `agentwatch purge <id> --yes` exposes it. Never hard-deletes
  (D-K); `verify()` stays green and other sessions are untouched.
- **Sink:** the daemon writes through the store and verifies the chain on startup.

## Requirements it satisfies

- R1 record every tool call · R6 local-first · R7 redaction-by-default · R11 tamper-evident.

## Sketch

- Append-only log of normalized records (one file per day/session) + an index for replay.
- Each entry references the previous entry's hash (hash chain) for tamper evidence (`DD-07`).
- Retention controls: size/time caps (v0.2.0, R11).
- No network required; OTLP exporter is opt-in (`DD-03`).

## Decisions

- **Store (C1 / DD-08):** append-only JSONL + hash chain for v0.1.0; Postgres for analytics in v0.2.0.
- **Hash-chain key (C2):** detect-only in v0.1.0.
- **Export gating (C4 / DD-09):** export blocked until a redaction self-test passes.
