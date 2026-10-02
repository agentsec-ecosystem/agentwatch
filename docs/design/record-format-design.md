# Design — Record Format & Security-Event Schema

**BLUF:** agentwatch normalizes every tool call into an OTel GenAI span and defines named, versioned
security events. This is the ecosystem's shared contract.

Status: **draft** (schema v1 targeted for v0.2.0 per the ecosystem roadmap; v0.1.0 records tool calls).

## Tool-call record (minimum fields)

- `session_id`, `agent_identity`, `harness`
- `tool.name`, `tool.arguments` (redacted by default), `tool.server` (MCP)
- `outcome` (ok/error/denied), `started_at`, `ended_at`, `duration_ms`
- trace context: W3C `trace_id` / `span_id`; OTel GenAI `execute_tool` span

## Security-event schema (named, versioned)

| Event | Emitted when | Emitter |
|---|---|---|
| `denied` | a tool call is blocked | agentpolicy |
| `policy-fired` | a policy decision is made (allow/deny/ask/rate-limit/redact) | agentpolicy |
| `secret-detected` | a secret/PII is detected (and redacted) | agentwatch / agentpolicy |
| `revoked` | a credential is revoked | agentkeys |
| `halted` | an agent is halted/paused | agenthalt |

## Open questions

- Event naming/versioning scheme (OTel event vs custom attribute)?
- Steward alone vs propose into OTel GenAI from day one (DD-05)?
