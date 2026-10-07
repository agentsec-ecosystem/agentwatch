# Design — OCSF & CloudEvents Mapping

**BLUF:** agentwatch emits its security events in two open standards a receiving side already speaks —
**OCSF** for SIEMs and **CloudEvents** for event buses. This is **export, not ingestion**: agentwatch
stays the source of truth and is not a SIEM (PRD 14). The mapping is pinned and tested so drift is
caught.

**Status:** published (v0.1.0) · **Milestone:** M20 S8 · Sources: [PRD 36](../prd/36-standards-and-interop.md),
[schema/security-event.schema.json](../../schema/security-event.schema.json).

## Pinned versions

- OCSF: **1.5.0** (`ocsf.OCSF_VERSION`), carried in `metadata.version`.
- CloudEvents: **1.0** (`ocsf.CLOUDEVENTS_VERSION`).

## Event-type mapping

| agentwatch event type | OCSF class | class_uid | category | activity | type_uid |
|---|---|---|---|---|---|
| `denied` | Authorize | 3003 | Identity & Access Management (3) | Deny (2) | 300302 |
| `policy-fired` | Detection Finding | 2004 | Findings (2) | Create (1) | 200401 |
| `secret-detected` | Data Security Finding | 2006 | Findings (2) | Create (1) | 200601 |
| `revoked` | Authorize | 3003 | Identity & Access Management (3) | Deny (2) | 300302 |
| `halted` | Detection Finding | 2004 | Findings (2) | Create (1) | 200401 |
| `drift-detected` | Detection Finding | 2004 | Findings (2) | Create (1) | 200401 |
| `tool-surface-changed` | Detection Finding | 2004 | Findings (2) | Create (1) | 200401 |
| `agent-delegation` | Detection Finding | 2004 | Findings (2) | Create (1) | 200401 |
| `recorder-config-changed` | Detection Finding | 2004 | Findings (2) | Create (1) | 200401 |
| `mode-transition` | Detection Finding | 2004 | Findings (2) | Create (1) | 200401 |
| `capability-changed` | Detection Finding | 2004 | Findings (2) | Create (1) | 200401 |

`type_uid = class_uid * 100 + activity_id`.

## Lossless-or-explicit

Fields OCSF cannot express natively are preserved verbatim under `unmapped`
(`event_version`, `emitter`, `policy_id`, `tool`, `credential_ref`, `evidence`, plus `session_id` and
`agentwatch_seq`). An event type with no mapping is still exported, flagged `unmapped_type: true` with
`type_uid: 0` — never dropped. `reason` becomes the OCSF `message`.

## CloudEvents envelope

```json
{
  "specversion": "1.0",
  "id": "denied|2026-01-02T03:04:05+00:00|s1|agentwatch",
  "source": "agentwatch",
  "type": "io.agentwatch.security-event.denied",
  "time": "2026-01-02T03:04:05+00:00",
  "subject": "s1",
  "datacontenttype": "application/json",
  "data": { "event_version": "0.1.0", "type": "denied", ... }
}
```

## CLI

`agentwatch export-session <id> --format ocsf|cloudevents` transcodes the session's security events to
NDJSON. It is read-only and local; no network.
