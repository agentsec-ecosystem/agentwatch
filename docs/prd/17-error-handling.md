# PRD 17 — Error Handling & Failure Modes

**BLUF:** Operational failures (not malicious tamper — that's the [threat model](../design/threat-model.md)).
Every failure mode has a detection, a default behavior (fail-closed), and a recovery path. Nothing fails
silently.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## Principle

**Fail closed, surface loudly.** A security recorder that silently stops recording is worse than no
recorder. Every failure is detectable by the operator and by agentwatch's own health endpoint (PRD 13).

## Failure modes

| # | Failure | Detection | Default behavior | Recovery |
|---|---|---|---|---|
| F1 | **Daemon crash** | health endpoint down; supervisor restart | supervisor restarts; gap is recorded as a session-boundary event | restart; replay shows the gap |
| F2 | **Hook fails to fire** (Claude Code hook error) | hook returns non-zero; daemon logs | the missed tool call is recorded as a `hook-error` record (not dropped) | fix the hook; re-run |
| F3 | **Store full** (size cap reached) | store monitor | **fail closed**: recording stops and surfaces; **no silent overwrite** | raise `store.max_size_mb` or run retention purge |
| F4 | **Corrupt hash chain** | `verify-store` on load/health | the broken link is reported; records after it are flagged untrusted | preserve evidence; re-initialize store; investigate (see [tamper-response](../runbooks/tamper-response.md)) |
| F5 | **Export failure** (OTLP endpoint down) | exporter retry/backoff | records keep accumulating locally; export retries | restore endpoint; export resumes; no data lost |
| F6 | **Redaction self-test fails** | self-test on startup and before export | **export blocked** (DD-09); recording continues locally | fix redaction config; re-run self-test |
| F7 | **Bad config** | validation on load/change | **fail closed**: daemon refuses to start (or stops + surfaces) | correct config; restart |
| F8 | **Adapter normalization error** | schema validation rejects the record | the raw event is quarantined with a `normalize-error` record (never silently dropped) | fix adapter; reprocess quarantined events |
| F9 | **Clock skew** (timestamps) | monotonic clock + UTC wall clock check | span durations use monotonic clock; wall-clock skew is logged | sync the system clock |
| F10 | **Partial session** (session boundary missed) | inactivity timeout closes the session | session is closed as `incomplete`; replay still works | none needed |

## Guarantees

- A recording gap is always **an event**, never an absence — operators can see "recording stopped here and
  resumed here" (the AgentObservatory "clean run vs couldn't read the run" lesson).
- Local records are **never lost** due to export failure (F5) — export is decoupled from storage.
- Quarantined/errored records (F2, F8) are kept for diagnosis, not hidden.

## Testing

Each failure mode has an injected-fault test in CI (part of the [testing & parity strategy](../plans/testing-and-parity-strategy.md)):
kill the daemon, fill the store, break the chain, drop the OTLP endpoint, poison the config, send a
malformed hook event. Each must fail closed and surface — not silently continue.
