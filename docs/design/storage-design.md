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

## Open questions

- Embedded store (SQLite) vs append-only JSONL for v0.1.0?
- Key management for the hash chain (none vs local key)?
