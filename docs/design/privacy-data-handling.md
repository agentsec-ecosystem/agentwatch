# Design — Privacy & Data Handling

**BLUF:** Local-first, redaction-by-default, and the four shipped privacy modes. Data leaves the host only
when the operator opts in — after a redaction self-test passes.

Status: **draft** (v0.1.0).

## Privacy modes (shipped, retained)

| Mode | Behavior |
|---|---|
| `metadata-only` (default) | Argument **shapes** recorded; values omitted |
| `truncated` | Values truncated to a bounded length |
| `hashed` | Values hashed (correlation without content) |
| `full` | Raw values (explicit opt-in; discouraged) |

## Data classes

Tool names/outcomes; argument shapes/values; MCP server ids; session/agent identity; timestamps; trace
context. Secrets/PII must never be persisted (R7).

## Retention

30-day default (R11); size/time caps; hash-chained.

## Egress

No network by default. OTLP export is opt-in and **blocked until a redaction self-test passes** (DD-09).

## Telemetry about the user

None. "Kept it on" is measured locally and shared voluntarily (DD-10, C7).
