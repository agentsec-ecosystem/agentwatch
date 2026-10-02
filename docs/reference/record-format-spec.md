# Reference — Record Format Spec (Normative)

**BLUF:** The normative contract for agentwatch records and security events. Machine-readable form:
[`../../schema/`](../../schema/). Changes follow the versioning/deprecation policy below.

## Record (v0.1.0)

| Field | Type | Req | Notes |
|---|---|---|---|
| `schema_version` | string | ✅ | `"0.1.0"` |
| `session_id` | string | ✅ | Groups a session |
| `trace_id` / `span_id` / `parent_span_id` | string | — | W3C trace context |
| `harness` | string | — | `claude-code`, `cursor`, `langgraph`, `python` |
| `agent.identity` | string | ✅ | Agent identity |
| `agent.{name,version,prompt_version,model_version,tool_schema_version,workload_type}` | string | — | Correlation dimensions |
| `tool.name` | string | ✅ | Tool name |
| `tool.server` | string | — | MCP server, if any |
| `tool.arguments` | object | — | **Redacted per privacy mode** |
| `tool.privacy_mode` | enum | — | metadata-only \| truncated \| hashed \| full |
| `outcome` | enum | ✅ | ok \| error \| denied |
| `started_at` / `ended_at` | date-time | ✅ / — | UTC |
| `duration_ms`, `tokens`, `cost_usd` | number | — | |
| `step_type` | enum | — | reason \| act \| observe \| verify |
| `security_event` | object | — | See below |

## Security event (v0.1.0)

`event_version`, `type` ∈ {`denied`, `policy-fired`, `secret-detected`, `revoked`, `halted`}, `emitted_at`,
`emitter`, optional `reason`, `policy_id`, `tool`, `credential_ref`, `evidence`.

## Python model (M2)

The normative contract is implemented in `agentwatch.records`: `AgentRecord`, `AgentIdentity`,
`ToolCall`, `SecurityEvent`, their enums, and the version constants `SCHEMA_VERSION` / `EVENT_VERSION`.
`validate_record()` and `validate_event()` are the validation entry points: strict, structural, and
**reject-never-coerce** (F8) — unknown keys, wrong types, bad enumerations, and unknown versions raise
`RecordValidationError` instead of being silently fixed. `to_dict()` / `from_dict()` round-trip
losslessly and are verified against [`../../schema/`](../../schema/) by the contract tests.

The `hook-error` convention (F2): a tool call whose hook could not be delivered is recorded, not dropped,
as a record with `outcome="error"` and `tool.name="hook-error"`.

## Versioning & deprecation policy

- Schema is versioned with `schema_version` / `event_version`.
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

### Decisions

- **Event naming/versioning (DD-14):** propose into OTel GenAI before locking schema v1.
- **Stewardship (DD-05):** contribute upstream; keep a repo-local copy until adopted.
- **Store (DD-08):** append-only JSONL + hash chain for v0.1.0.
