# Schema changelog

All notable changes to the published schemas. The policy check
(`agentwatch.schema_policy`) requires the current schema version to appear here.

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
