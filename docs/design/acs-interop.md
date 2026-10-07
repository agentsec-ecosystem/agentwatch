# Design — ACS (Agent Control Standard) Guardian ingest

**BLUF:** The Agent Control Standard (ACS) defines a JSON-RPC 2.0 channel between
an Observed Agent and a **Guardian** that permits/denies/modifies each step. This
design ingests a Guardian's **audit trail** so its decisions become agentwatch
security events with AAT `record_phase: pre_execution` — the Guardian decides
*before* the action it gates.

Status: implemented (M29 ACS-1, #367). **Ingest-first; monitor-only.** The
emit-side spike (PRD 45 §ACS-1b) is not built.

## Why

Guardian decisions are our security events with pre-execution provenance. Reusing
the open security-event schema (never a new schema) lets a Guardian's enforcement
outcome be correlated with the hook record of the same session.

## The wire shape we ingest (pinned revision)

ACS v0.1.0 is JSON-RPC 2.0. An Observed Agent sends, e.g.:

```json
{
  "jsonrpc": "2.0",
  "method": "steps/toolCallRequest",
  "id": "req-001",
  "params": {
    "acs_version": "0.1.0",
    "request_id": "550e8400-…",
    "timestamp": "2026-04-30T10:30:00Z",
    "metadata": {"agent_id": "cursor-agent-01", "session_id": "7c9e6679-…"},
    "payload": {"tool": {"name": "email.send"}, "capability": "network.egress"}
  }
}
```

The Guardian returns a decision envelope:

```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "result": {
    "type": "final", "acs_version": "0.1.0", "request_id": "550e8400-…",
    "decision": "deny", "reasoning": "…",
    "reason_codes": ["fides_p_t_failed"],
    "policy_references": [{"policy_id": "acme-baseline", "rule_id": "…"}]
  }
}
```

`agentwatch ingest <trail> --format acs` accepts a `{"messages": [...]}` bundle, a
list of frames, a single frame, or a JSON string; each decision response is paired
to its request by `id` / `request_id`.

## Mapping

| ACS | agentwatch |
|---|---|
| `decision=deny` | `outcome=denied` + `SecurityEventType.denied` |
| `decision=modify` / `ask` / `defer` | `SecurityEventType.policy-fired` |
| `decision=allow` | record only (no security event) |
| `record_phase` | `pre_execution` (never inferred from outcome) |
| `metadata.session_id` | `session_id` |
| `metadata.agent_id` | `agent_identity.identity` |
| `payload.tool.name` | `tool.name` |
| `policy_references[0].policy_id` | `security_event.policy_id` |
| `reasoning` / `reason_codes` | `security_event.reason` / `evidence` |

Every record carries `environment.source == "acs"`,
`environment.monitor_only == true`, and the pinned `acs_version`.

## Posture

- **Monitor-only.** `MONITOR_ONLY` is a guarantee: agentwatch records a decision
  and never executes it — enforcement stays in the Guardian. `EMIT_SIDE_BUILT` is
  `False` (the emit-side spike is deferred).
- **Version-pinned + drift.** `ACS_VERSION = "0.1.0"`; `check_acs_drift` compares
  the pinned revision and the mapped fields against an upstream descriptor (the
  AAT-5 pattern). A revision bump, or an upstream drop of a mapped field, is drift.
- **Reject-never-invent.** An unknown revision, method (not one of the 19
  `steps/*` hooks or a `protocols/MCP/*` wrap), or decision is a problem the
  caller quarantines (B4) — never guessed. A decision frame with no matching
  request is quarantined.
- **Foreign input.** The trail is untrusted: content is masked through the secrets
  pipeline before storage (DD-06); a secret in the trail surfaces as a
  `secret-detected` observation.

## Non-goals

- We do **not** verify ACS signatures or the SessionContext audit chain (the
  Crypto/Audit profiles). The Guardian is the authority; we record its output.
- We do **not** emit ACS-compatible observations yet (spike deferred, PRD 45
  §ACS-1b).

## References

- PRD 45 §ACS-1 (`docs/prd/45-new-capture-surfaces.md`)
- ACS v0.1.0 (`GenAI-Security-Project/agent-control-standard`)
- AAT `record_phase` (PRD 41) — `docs/design/aat-mapping.md`
