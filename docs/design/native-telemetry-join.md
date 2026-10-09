# Design — Native Telemetry Join

**BLUF:** How agentwatch ingests a harness's **own** OpenTelemetry (Claude Code first: metrics/events/traces) and joins
it to hook records by `tool_use_id`, replacing inference with authoritative facts (exact tokens/cost/latency, and the
permission decision source that feeds [authorization provenance](authorization-provenance-v2.md)). Disagreements are
classified observations; the hook path stays the zero-config default.

**Status:** implemented (CCO-1/CCO-2 2026-10-06) · **Milestone:** M29 · Sources:
[PRD 51](../prd/51-harness-native-telemetry-and-framework-reach.md), [otel-mapping.md](otel-mapping.md),
[observability.md](observability.md).

## Why

The plan ingests Gemini's OTel, Cursor hooks and the Compliance API — not the home harness. Claude Code already exports
`user_prompt`, `api_request`, `tool_result`, `tool_decision` (with `decision_source`), `permission_mode_changed` and
`mcp_server_connection`, correlated by `tool_use_id`/`prompt.id`, plus beta traces. Cost is currently extracted from
transcripts; native telemetry is exact and authoritative.

## Ingest & join

1. Receive logs/metrics/traces (local listener or file; OTLP/gRPC or JSON per PRD 41 OTEL-3).
2. Map into the record/event model (semconv-pinned; see otel-mapping).
3. **Join** to hook records by `tool_use_id`. A record may be: hook-only, otel-only, or joined.
4. Record a discrepancy observation when the two sources disagree (e.g. outcome, cost, decision) — never silently reconcile.

`coverage` reports the join rate and discrepancy count.

## Framework reach (FWK-1)

The same transcoder is the framework on-ramp: ADK and Strands emit OTel GenAI
natively, the OpenAI Agents SDK emits via Arize OpenInference, and the Claude Agent
SDK emits the shared Claude Code stream. A recipe only sets the standard OTLP
endpoint (or installs the community instrumentor); it does **not** add an adapter.
The attribute vocabulary is explicit — `gen_ai.*` (GenAI) and `openinference.*` /
`llm.*` (OpenInference) — and any key the transcoder does not consume is returned in
an explicit `unmapped` bucket so a framework's attribute drift is visible, never
silently dropped. Recipes, pins and tiers live in
[`reference/framework-recipes.md`](../reference/framework-recipes.md).

## What native telemetry provides

| Fact | Source event | Consumed by |
|---|---|---|
| exact tokens/cost/latency/cache | `api_request`, `tool_result` | `cost` (S6), OUT |
| permission decision source | `tool_decision.decision_source` | authorization v2 (APV-1) |
| permission mode changes | `permission_mode_changed` | APV-2 |
| MCP server connection | `mcp_server_connection` | inventory (CAP) |

## Privacy

- `cost` stamps each figure `exact (vendor)` vs `estimated (pricing-table vN)`.
- Prompt text / tool details are ingested **only** if the user enabled them in the harness *and* the privacy mode
  permits; redaction runs on ingest regardless. Metadata-only default unchanged.
- Foreign/unmappable input → B4 quarantine.

## Testing

- ≥95% join rate on the field corpus; discrepancies classified (FT-CCO-1).
- Cost split shown correctly for mixed exact/estimated.
- No prompt content in the store when the harness has details off.
- Fixtures version-tagged per Claude Code version; drift job flags attribute changes.

## Decision

ADR-0031 — join semantics, discrepancy policy, and privacy of ingested events. Extends the D-Q transcoder stance (no
storage backend).
