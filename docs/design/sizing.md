# Design — Sizing & Volume

**BLUF:** Expected record volumes and storage growth, so retention and caps are grounded, not guessed.

Status: **draft** (v0.1.0).

## Assumptions

- A Claude Code session: ~50–500 tool calls/day for an active developer.
- Record size (metadata-only): ~0.5–2 KB.

## Volume

| Scenario | Tool calls/day | Records/day | Storage/day |
|---|---|---|---|
| Light user | 50 | 50 | ~100 KB |
| Active developer | 500 | 500 | ~1 MB |
| Power user / CI | 5,000 | 5,000 | ~10 MB |

## Retention (R11, default)

- 30 days × ~1 MB/day (active) ≈ 30 MB; under the 1024 MB cap with large headroom.
- Caps: `retention_days=30`, `max_size_mb=1024` (PRD 16). Purge is tombstoned, not silent (PRD 15).

## Fleet (v1.0+; v0.1.0 is single-host)

- Multi-host aggregation is opt-in (R13) and out of scope for v0.1.0 sizing.
