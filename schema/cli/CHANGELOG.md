# CLI JSON schema changelog

All notable changes to the published CLI JSON contract. The guard
(`agentwatch.cli_schema`) requires the current `CLI_SCHEMA_VERSION` to appear
here and every registered read command to have a schema.

## v0.1.0 — 2026-10-07

Initial published contract (M30 AGI-2). One versioned JSON Schema per
read/investigation command's `--json` output:

- `search.schema.json` — record object per line (NDJSON).
- `replay.schema.json` — array of `{record}` (optional `receipt`).
- `impact.schema.json` — change-footprint report.
- `blame.schema.json` — path-touch report.
- `coverage.schema.json` — store-vs-transcript coverage.
- `cost.schema.json` — token/cost rollup.
- `oversight.schema.json` — human-oversight report.
- `inventory.schema.json` — agent / MCP-server inventory.
- `diff.schema.json` — behavioral diff of two sessions.
- `trace.schema.json` — cross-host causal trace.
- `tree.schema.json` — subagent fan-out tree.
- `flow.schema.json` — content→argument flow edges.
- `secrets.schema.json` — secret traces.
