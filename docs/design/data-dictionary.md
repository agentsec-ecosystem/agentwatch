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

## Derived index (rebuildable) — `schema/derived-index.sql`

The fleet/multi-tenant query tier is a **derived** Postgres index ([derived-postgres](derived-postgres.md)):
it is rebuilt from the chain and may be dropped at any time. The DDL lives in
[`schema/derived-index.sql`](../../schema/derived-index.sql). Every table carries `source_seq` and
`source_hash` back-references so a row always traces to the chain entry it came from — the chain remains the
source of truth, and no query here authorizes data the store cannot reproduce.

| Table | Purpose | Key + back-ref columns |
|---|---|---|
| `sessions` | one agent session | `session_id`, `project`, `harness`, `agent_name`, `agent_version`, `source_seq`, `source_hash` |
| `records` | tool/behavior records | `record_id`, `session_id`, `seq`, `tool`, `outcome`, `record_phase`, `source_seq`, `source_hash` |
| `events` | security events | `event_id`, `session_id`, `type`, `emitter`, `source_seq`, `source_hash` |
| `usage` | tokens / cost / duration rollups | `usage_id`, `session_id`, `tokens`, `cost_usd`, `duration_ms`, `source_seq`, `source_hash` |
| `identity` | the `agent_identity` dimension | `identity_id`, `session_id`, `credential_class`, `workload_identity`, `principal_hash`, `delegation_chain`, `source_seq`, `source_hash` |
| `detectors` | anomaly findings | `finding_id`, `session_id`, `detector`, `severity`, `explanation`, `source_seq`, `source_hash` |

## Record & security-event contract (v0.2.0 additions)

The normative field contract is the [record-format spec](../reference/record-format-spec.md) and
[`agentwatch.records`](../../packages/python-sdk/src/agentwatch/records.py); this is the dictionary of the
v0.2.0 additive fields. All are optional; absent means an honest default, never a coerced value.

| Field | Type | Meaning | Default when absent |
|---|---|---|---|
| `record_phase` | enum `pre_execution` \| `post_execution` \| `unknown` | Whether a decision preceded execution (AAT-1) | `unknown` (`effective_record_phase`) |
| `traceparent` | string | W3C Trace Context traceparent for cross-agent/host correlation (TRACE-1) | — |
| `agent.workload_identity` | string | SPIFFE/WIMSE workload-identity URI (IDN-1) | — |
| `agent.credential_class` | enum `api-key` \| `oauth` \| `svid` \| `ambient/shared` | Credential classification (IDN-1) | — |
| `agent.principal` | string | On-behalf-of principal; hashed by default in metadata-only (IDN-1) | — |
| `agent.delegation_chain` | string[] | On-behalf-of chain; principals hashed by default (IDN-1) | — |
| `authorization.source` | enum `human-once` \| `human-remembered` \| `rule` \| `classifier` \| `hook` \| `bypass` \| `not-required` \| `denied` \| `unknown` | Who/what authorized the call (M29 APV-1, `authz-v2`) | `unknown` (`effective_authorization`) |
| `authorization.deny` | enum `human` \| `rule` \| `classifier` \| `hook` \| `unknown` | Who/what refused when `source=denied` (M29 APV-1) | — |
| `authorization.evidence` | enum `harness-native` \| `inferred` \| `session-mode` | How the source was established (M29 APV-1) | — |
| `permission_mode` | enum `default` \| `acceptEdits` \| `plan` \| `auto` \| `dontAsk` \| `bypassPermissions` \| `unknown` | Mode in force at the call, time-varying (M29 APV-2) | `unknown` (`effective_permission_mode`) |
| `security_event.type` | enum | Adds `agent-delegation` (A2A-2): delegation observed, never an authorization verdict | — |

Versioning: `schema_version` / `event_version` accept the supported range `0.1.0`–`0.2.0`; the current
emit version stays `0.1.0` until the v0.2.0 release bump (M30 30.3). The emit/supported pair lives in
[`agentwatch.records`](../../packages/python-sdk/src/agentwatch/records.py).

## Notes

- Version dimensions: `prompt_version`, `model_version`, `tool_schema_version` (optional).
- Timestamps UTC; costs in USD; retention 30 days default.
