# PRD 15 — Data Model & Lifecycle

**BLUF:** The core entities (record, session, run, span, anomaly, cohort, security event), their identities,
and their lifecycle from creation to purge. One home for what's currently split across the schema, the
record-format spec, and the data dictionary.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## Entities

| Entity | Identity | Defined in |
|---|---|---|
| **Record** | `<session_id>:<span_id>` | [record-format spec](../reference/record-format-spec.md), [schema](../../schema/agent-record.schema.json) |
| **Session** | `session_id` (string, harness-supplied or generated) | groups a recording session |
| **Run** | `run_id` (UUID v7, time-ordered) | one agent execution within a session; surfaced in v0.2.0 analytics |
| **Span** | `span_id` (W3C, 16-byte hex) | a unit of work; tool calls are `execute_tool` spans |
| **Security event** | `<event_version>:<type>:<span_id>:<seq>` | [schema](../../schema/security-event.schema.json) |
| **Anomaly** | `anomaly_id` (UUID) | produced by a detector; `severity`, `explanation`, `evidence` |
| **Cohort** | `<agent_name>:<agent_version>:<workload_type>:<window>` | version comparison unit (v0.3.0+) |

## Identity & versioning scheme

- **IDs** — `session_id` harness-supplied (stable across replays); `run_id`/`span_id` generated; `span_id`
  follows W3C Trace Context.
- **Schema versions** — `schema_version` (records) and `event_version` (security events), both SemVer.
  Additive changes bump minor; breaking changes bump major + a deprecation cycle (see
  [record-format spec §Versioning](../reference/record-format-spec.md)).
- **Agent dimensions** — `agent_name`, `agent_version`, optional `prompt_version`, `model_version`,
  `tool_schema_version`, `workload_type` (carried for cohort comparison).
- **Capture-fidelity fields (M9)** — records carry an optional `project` (the event cwd) for per-project
  filtering and `parent_session_id` linking resumed/forked sessions to their logical parent.

## Record lifecycle

```
created (normalized + redacted) → stored (hash-chained) → [exported, opt-in] → retained → purged
```

| State | Trigger | Guarantees |
|---|---|---|
| **created** | adapter event normalized + redacted (DD-06) | schema-valid; no secrets |
| **stored** | appended to local store; chained (DD-07) | append-only; hash chain intact |
| **exported** | OTLP exporter forwards (opt-in, gated on redaction self-test, DD-09) | backend receives OTel GenAI spans + events |
| **retained** | within retention window (30-day default, R11) | queryable; replayable |
| **purged** | retention cap reached (size/time) or `agentwatch purge <id>` | removed; chain tombstoned (no silent gap) |

## Session & run lifecycle

- A **session** opens on the first recorded event and closes on an explicit boundary (harness session end)
  or an inactivity timeout. Sessions are immutable once closed.
- A **run** is a unit of agent execution within a session (one invocation of `@trace_agent` or one hook
  stream). Runs are the analytics unit (cost, retries, success rate) from v0.2.0.

## Security-event lifecycle

Emitted at decision time by the emitter (agentwatch / agentpolicy / agentkeys / agenthalt); attached to the
relevant span; stored and exported with it. Events are immutable; corrections are new events, not edits.

## Invariants

- No record is ever mutated or deleted except by retention purge (which tombstones, not silently removes).
- The hash chain is continuous; any break is surfaced, never silent (NFR-8, fail-closed).
- No secret/PII is ever persisted (R7, DD-06) regardless of lifecycle state.
