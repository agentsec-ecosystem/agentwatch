# Design — Local Storage

**BLUF:** Local-first, append-only record store with hash-chaining; export is opt-in.

Status: **draft**.

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
