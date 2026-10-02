# Design — Data Dictionary (analytics store)

**BLUF:** The Postgres tables used by the analytics/API layer (v0.2.0+), retained from the shipped project
(DD-12). The v0.1.0 local store is JSONL (DD-08).

Status: **draft** (v0.2.0+). The v0.1.0 record contract itself is in
[`agentwatch.records`](../../packages/python-sdk/src/agentwatch/records.py) and the
[record-format spec](../reference/record-format-spec.md).

| Table | Key fields |
|---|---|
| `runs` | `run_id`, `agent_name`, `agent_version`, `workload_type`, `started_at`, `ended_at`, `status`, `cost`, `tokens` |
| `spans` | `span_id`, `run_id`, `parent_span_id`, `name`, `kind`, `started_at`, `duration_ms`, `attributes` |
| `anomalies` | `anomaly_id`, `run_id`, `detector`, `category`, `severity`, `explanation`, `evidence` |
| `cohorts` | `agent_name`, `agent_version`, `window_start`, `run_count`, `cost`, `retry_rate`, `success_rate` |
| `fleet_rollup` | `agent_name`, `run_count`, `anomaly_count`, `status` |

## Notes

- Version dimensions: `prompt_version`, `model_version`, `tool_schema_version` (optional).
- Timestamps UTC; costs in USD; retention 30 days default.
