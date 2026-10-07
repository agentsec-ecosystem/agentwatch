# Schema changelog

All notable changes to the published schemas. The policy check
(`agentwatch.schema_policy`) requires the current schema version to appear here.

## 0.2.0 (schema range; additive) — 2026-10-05

Additive minor (W5 schema stewardship): old readers keep working; new optional
fields are absent on 0.1.0 records and read with an honest default. The
`schema_version` / `event_version` **range** is extended to `0.2.0`; the current
emit version stays `0.1.0` until the v0.2.0 release bump (M30 30.3).

- `agent-record.schema.json` `schema_version` accepts `0.1.0` and `0.2.0`.
  New optional fields: `record_phase` (`pre_execution` \| `post_execution` \|
  `unknown`, AAT-1), `traceparent` (W3C Trace Context, TRACE-1), and the
  `agent_identity` dimension on `agent` (IDN-1): `workload_identity`,
  `credential_class` (`api-key` \| `oauth` \| `svid` \| `ambient/shared`),
  `principal`, `delegation_chain`.
- `agent-record.schema.json` new optional `authorization` object (M29 APV-1,
  PRD 49): `source` (`human-once` \| `human-remembered` \| `rule` \| `classifier`
  \| `hook` \| `bypass` \| `not-required` \| `denied` \| `unknown`), `deny`
  (`human` \| `rule` \| `classifier` \| `hook` \| `unknown`), `evidence`
  (`harness-native` \| `inferred` \| `session-mode`). Additive; legacy `approval`
  is mapped at read time and never written back.
- `agent-record.schema.json` new optional `permission_mode` (M29 APV-2, PRD 49):
  `default` \| `acceptEdits` \| `plan` \| `auto` \| `dontAsk` \|
  `bypassPermissions` \| `unknown`. Additive; mode transitions are their own
  `permission-mode-changed` observations, and a missing mode reads as `unknown`.
- `security-event.schema.json` `event_version` accepts `0.1.0` and `0.2.0`;
  new event type `agent-delegation` (A2A-2, PRD 45) — an observation of a
  cross-agent delegation, never an authorization verdict.
- `security-event.schema.json` (M29 EXT-3) adds `recorder-config-changed`
  (DEP-2, PRD 50 — the effective recorder config digest changed; digests/
  booleans only), `mode-transition` (APV-2, PRD 49 — an observed permission-mode
  transition), and `capability-changed` (a forward-compatible placeholder for
  M30 CAP-2, not built). OCSF/CloudEvents mappings and fixtures updated; the
  `agentwatch.security-event` readers accept them additively.

## 0.1.0 — 2026-10-03

Initial published contract.

- `agent-record.schema.json` `schema_version` `0.1.0`: the tool-call / behavior
  record. Additive optional fields shipped during v0.1.0 (unreleased):
  `producer` (M15 S26), `approval` and `environment` (M19 S14/S16/S29),
  `truncated` (M21 S36).
- `security-event.schema.json` `event_version` `0.1.0`: the named event
  vocabulary — `denied`, `policy-fired`, `secret-detected`, `revoked`, `halted`,
  `drift-detected`, and `tool-surface-changed` (added via the M22 W5 process,
  first shipped in M20 S4).
