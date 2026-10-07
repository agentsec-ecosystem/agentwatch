# Reference — Record Format Spec (Normative)

**BLUF:** The normative contract for agentwatch records and security events. Machine-readable form:
[`../../schema/`](../../schema/). Changes follow the versioning/deprecation policy below.

## Record (v0.2.0 additions)

Additive minor: new optional fields (rows below) are absent on older records and read with an honest
default. The schema version range is `0.1.0`–`0.2.0`; the current emit version stays `0.1.0` until the
v0.2.0 release bump (M30 30.3), so `0.2.0` is accepted for forward compatibility.

| Field | Type | Req | Notes |
|---|---|---|---|
| `schema_version` | string | ✅ | `"0.1.0"` \| `"0.2.0"` (current emit: `"0.1.0"`) |
| `session_id` | string | ✅ | Groups a session |
| `trace_id` / `span_id` / `parent_span_id` | string | — | W3C trace context |
| `traceparent` | string | — | W3C Trace Context traceparent (TRACE-1, additive 0.2.0) |
| `harness` | string | — | `claude-code`, `cursor`, `langgraph`, `python` |
| `host` | string | — | Originating host tag for fleet aggregation (M11 R13); additive |
| `producer` | object | — | Provenance (M15 S26): `{kind, name?, version?}`. `kind` ∈ `hook` \| `import` \| `event` \| `ingest` \| `proxy` \| `sdk` \| `demo`. Optional/additive: records written before the field are read as an inferred `kind: "hook"` and are never rewritten silently. |
| `agent.identity` | string | ✅ | Agent identity |
| `agent.{name,version,prompt_version,model_version,tool_schema_version,workload_type}` | string | — | Correlation dimensions |
| `agent.{workload_identity,principal}` | string | — | `agent_identity` dimension (IDN-1). `workload_identity` is a SPIFFE/WIMSE URI; `principal` is hashed by default in metadata-only. Never secret material. |
| `agent.credential_class` | enum | — | `api-key` \| `oauth` \| `svid` \| `ambient/shared` (IDN-1) — a classification, never a credential value |
| `agent.delegation_chain` | string[] | — | On-behalf-of chain (IDN-1); principals hashed by default; absent when the harness does not expose it (honest `unknown`) |
| `tool.name` | string | ✅ | Tool name |
| `tool.server` | string | — | MCP server, if any |
| `tool.arguments` | object | — | **Redacted per privacy mode** |
| `tool.response` | object | — | **Redacted tool result per privacy mode** (M6 additions) |
| `tool.privacy_mode` | enum | — | metadata-only \| truncated \| hashed \| full |
| `outcome` | enum | ✅ | ok \| error \| denied |
| `started_at` / `ended_at` | date-time | ✅ / — | UTC |
| `duration_ms`, `tokens`, `cost_usd` | number | — | |
| `step_type` | enum | — | reason \| act \| observe \| verify |
| `record_phase` | enum | — | `pre_execution` \| `post_execution` \| `unknown` (AAT-1, additive 0.2.0). Absent on legacy records and read as `unknown` (`effective_record_phase`); never inferred from `outcome`. |
| `approval` | enum | — | Who authorized the call (M19 S14): `user` \| `auto` \| `not-required` \| `denied` \| `unknown`. Optional/additive: absent means `unknown` on read (`effective_approval`); only written when the harness exposed a decision. |
| `environment` | object | — | Metadata-only session-start snapshot (M19 S16/S29): `{vcs, harness?, os?, agentwatch?, context, principal?}`. No env-var values. |
| `truncated` | object | — | Visible truncation marker when a pathological record exceeded a limit (M21 S36): `{fields:[{field, original_bytes, rule}], record_bytes?}`. Truncation is never silent. |
| `security_event` | object | — | See below |

## Security event (v0.2.0 additions)

`event_version` range is `0.1.0`–`0.2.0` (current emit `0.1.0`). `type` ∈ {`denied`, `policy-fired`, `secret-detected`,
`revoked`, `halted`, `drift-detected`, `tool-surface-changed`, `agent-delegation`, `recorder-config-changed`,
`mode-transition`, `capability-changed`}, `emitted_at`,
`emitter`, optional `reason`, `policy_id`, `tool`, `credential_ref`, `evidence`.

`agent-delegation` (A2A-2, PRD 45, additive) is an **observation** that a cross-agent
delegation occurred — never an authorization verdict.

`recorder-config-changed` (M29 DEP-2, PRD 50) is an observation that the effective recorder hook/permission config
digest changed; its `evidence` carries the two keyed digests and the changed booleans only — **never** config values.

`mode-transition` (M29 APV-2, PRD 49; also produced by WS-A) is an observation of a permission-mode transition
(e.g. `default` → `bypass` → `default`), reconstructed from the record stream.

`capability-changed` (M29 EXT-3) is a **forward-compatible placeholder**: it is in the vocabulary and mappings so
sinks and consumers stay stable, but the event originates in **M30 CAP-2** (capability inventory, not built).

## Python model (M2)

The normative contract is implemented in `agentwatch.records`: `AgentRecord`, `AgentIdentity`,
`ToolCall`, `SecurityEvent`, their enums, and the version constants `SCHEMA_VERSION` / `EVENT_VERSION`.
`validate_record()` and `validate_event()` are the validation entry points: strict, structural, and
**reject-never-coerce** (F8) — unknown keys, wrong types, bad enumerations, and unknown versions raise
`RecordValidationError` instead of being silently fixed. `to_dict()` / `from_dict()` round-trip
losslessly and are verified against [`../../schema/`](../../schema/) by the contract tests.

The `hook-error` convention (F2): a tool call whose hook could not be delivered is recorded, not dropped,
as a record with `outcome="error"` and `tool.name="hook-error"`.

**Provenance (M15 S26).** Every new record carries a `producer` object naming how it entered the store:
live hooks (`hook`), transcript import (`import`), `event emit` (`event`), OTel/NDJSON ingestion
(`ingest`), MCP interposition (`proxy`), or SDK/test emitters (`sdk`). `effective_producer()` returns the
stored value, or infers `hook` for a legacy record (reported by `producer_is_inferred()`); the inferred
value is never written back. `search --producer <kind>` filters on it, and reject-never-coerce applies:
an unknown `kind` raises `RecordValidationError`.

## Versioning & deprecation policy

- Schema is versioned with `schema_version` / `event_version`.
- The current version is what new records/events are emitted with; readers accept a **supported range**
  (`records.SUPPORTED_SCHEMA_VERSIONS` / `SUPPORTED_EVENT_VERSIONS`) and reject an unknown version with
  the range named, never coercing it.
- Additive changes bump the minor version; breaking changes bump the major and require a deprecation cycle
  (≥1 minor release of dual-emit or a documented migration).
- Naming/versioning is proposed upstream to OTel GenAI before lock (DD-14).

## Privacy

No secret/PII is ever persisted (`DD-06`); values follow the privacy modes in
[privacy-data-handling](../design/privacy-data-handling.md).

---

## Design rationale & status (merged from the former design doc)

**Status:** shipped (M2) — the normative contract above is authoritative; the Python model lives in
`agentwatch.records`. This section records rationale.

### Security-event emitters

| Event | Emitted when | Emitter |
|---|---|---|
| `denied` | a tool call is blocked | agentpolicy |
| `policy-fired` | a policy decision (allow/deny/ask/rate-limit/redact) | agentpolicy |
| `secret-detected` | a secret/PII is detected (and redacted) | agentwatch / agentpolicy |
| `revoked` | a credential is revoked | agentkeys |
| `halted` | an agent is halted/paused | agenthalt |
| `drift-detected` | a metric deviates from its trailing baseline (observation only) | agentwatch (M11) |
| `recorder-config-changed` | the effective recorder hook/permission config digest changed (M29 DEP-2) | agentwatch |
| `mode-transition` | an observed permission-mode transition (M29 APV-2) | agentwatch |
| `capability-changed` | a capability inventory digest changed (placeholder; M30 CAP-2) | agentwatch (reserved) |

### Decisions

- **Event naming/versioning (DD-14):** propose into OTel GenAI before locking schema v1.
- **Stewardship (DD-05):** contribute upstream; keep a repo-local copy until adopted.
- **Store (DD-08):** append-only JSONL + hash chain for v0.1.0.
